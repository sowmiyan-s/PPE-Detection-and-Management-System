"""
Stage 1 + 2 + 3 – Person detection & tracking, PPE detection, and association.

Combines YOLOv8 ByteTrack (Stage 1), multi-class PPE detection (Stage 2),
body-region-aware association (Stage 3), zone rule evaluation (Stage 4), and
temporal validation (Stage 5) via PPEMqttPublisher.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Optional

import cv2
import numpy as np

# PyTorch 2.6+ compatibility – must be patched before ultralytics import
import torch
_orig_torch_load = torch.load
def _safe_torch_load(f, *args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _orig_torch_load(f, *args, **kwargs)
torch.load = _safe_torch_load

from ultralytics import YOLO

from src.core import config
from src.core.association import associate_ppe_to_persons
from src.core.publisher import PPEMqttPublisher
from src.core.rule_engine import RuleEngine
from src.core.worker_tracker import WorkerTracker, POSITIVE_PPE
from src.core.temporal_validator import TemporalValidator

log = logging.getLogger(__name__)

# ── Class definitions (must match data.yaml) ────────────────────────────────

ALL_PPE_CLASSES: set[str] = {
    "Boots", "Ear-Protection", "Glass", "Glove", "Hard_hat", "Mask",
    "No-Boots", "No-Ear-Protection", "No-Glass", "No-Glove", "No-Helmet",
    "No-Mask", "No-Vest", "Vest", "Circular_Saw", "Fire_Extinguisher",
    "Fire_prevention_Net", "Welding_Equipment",
    "helmet", "no-helmet", "vest", "no-vest", "gloves", "no-gloves", "boots", 
    "no-boots", "goggles", "no-goggles", "ear-mufs", "face-guard", "safety-suit",
    "tool", "safety_hook"
}

COMPLIANCE_COLOURS = {
    True:  (0, 200, 0),    # green  – compliant
    False: (0, 0, 220),    # red    – violation
}


class PPEDetector:
    """
    Full per-frame PPE compliance detector.

    Usage
    -----
    detector = PPEDetector()
    annotated_frame, worker_states = detector.process_frame(frame, zone="work_at_height")
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        zone:       str           = config.DEFAULT_ZONE,
        broker:     str           = config.MQTT_BROKER,
        port:       int           = config.MQTT_PORT,
        topic:      str           = config.MQTT_TOPIC,
    ) -> None:
        # ── Model ──────────────────────────────────────────────────────────────
        if model_path is None:
            model_path = config.DEFAULT_MODEL_PATH
        if not os.path.exists(model_path):
            log.warning("Custom model not found at %s, using fallback %s",
                        model_path, config.FALLBACK_MODEL_PATH)
            model_path = config.FALLBACK_MODEL_PATH

        # Jetson / TensorRT auto-fallback: if we requested a .pt but a .engine exists, use it.
        engine_path = model_path.replace('.pt', '.engine')
        if os.path.exists(engine_path):
            log.info("Found TensorRT engine at %s, preferring it for max performance.", engine_path)
            model_path = engine_path

        self.model       = YOLO(model_path)
        self.default_zone = zone

        # ── Supporting components ───────────────────────────────────────────────
        self._publisher = PPEMqttPublisher(broker=broker, port=port, topic=topic)
        self._rule_engine = RuleEngine()
        self._worker_tracker = WorkerTracker()
        self._temporal_validator = TemporalValidator()
        self._lock = threading.Lock()
        
        self._track_memory: dict[int, dict] = {}  # track_id -> {"box": list, "last_frame": int}
        self._frame_count: int = 0
        self._next_synthetic_id: int = 101

        # Adaptive frame-skip cache for low-end CPU systems
        self._last_worker_states: list[dict] = []
        self._last_persons: list[dict] = []
        self._last_ppe_items: list[dict] = []

    def update_zone_rule(self, zone_name: str, required_ppe: set[str]) -> None:
        """Update required PPE rules for a zone at runtime."""
        with self._lock:
            self._rule_engine.add_zone(zone_name, required_ppe)
            config.ZONE_RULES[zone_name] = required_ppe
            log.info("PPEDetector updated zone '%s' rules to: %s", zone_name, required_ppe)

    @staticmethod
    def _compute_walk_robust_similarity(boxA: list[float], boxB: list[float]) -> float:
        if not boxA or not boxB or len(boxA) < 4 or len(boxB) < 4:
            return 0.0
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])
        interArea = max(0.0, xB - xA) * max(0.0, yB - yA)
        boxAArea = max(1e-5, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
        boxBArea = max(1e-5, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))
        
        iou = interArea / float(boxAArea + boxBArea - interArea)
        minArea = min(boxAArea, boxBArea)
        containment = interArea / float(minArea) if minArea > 0 else 0.0
        
        cxA, cyA = (boxA[0] + boxA[2]) / 2.0, (boxA[1] + boxA[3]) / 2.0
        cxB, cyB = (boxB[0] + boxB[2]) / 2.0, (boxB[1] + boxB[3]) / 2.0
        max_dim = max(boxA[2] - boxA[0], boxA[3] - boxA[1], boxB[2] - boxB[0], boxB[3] - boxB[1], 100.0)
        dist = ((cxA - cxB) ** 2 + (cyA - cyB) ** 2) ** 0.5
        center_sim = max(0.0, 1.0 - (dist / (max_dim * 1.5)))

        return max(iou, containment * 0.75, center_sim * 0.65)

    # ── Public API ─────────────────────────────────────────────────────────────

    def process_frame(
        self,
        frame: np.ndarray,
        zone:  Optional[str] = None,
    ) -> tuple[np.ndarray, list[dict]]:
        """
        Run the full 5-stage pipeline on one video frame.

        Returns
        -------
        annotated_frame : BGR frame with bounding boxes and status overlays
        worker_states   : list of dicts, one per tracked worker
        """
        self._frame_count += 1
        active_zone = zone or self.default_zone

        # Low-end CPU adaptive frame skip check: reuse cached detections on skipped frames
        if config.FRAME_SKIP_INTERVAL > 0 and (self._frame_count % (config.FRAME_SKIP_INTERVAL + 1) != 0) and self._last_worker_states:
            for person in self._last_persons:
                compliant = next((w["compliant"] for w in self._last_worker_states if w.get("worker_id") == f"Worker-{person['id']}"), True)
                missing = next((set(w.get("missing_ppe", [])) for w in self._last_worker_states if w.get("worker_id") == f"Worker-{person['id']}"), set())
                self._draw_person(frame, person, compliant, missing, [])
            for ppe in self._last_ppe_items:
                self._draw_ppe(frame, ppe)
            return frame, self._last_worker_states

        # ── Stage 1+2: detect + track (raw frame — no enhancer for speed) ────
        try:
            results = self.model.track(
                frame,
                persist=True,
                tracker=config.TRACKER_CONFIG,
                conf=config.DETECTION_CONF,
                imgsz=config.INFERENCE_IMG_SIZE,
                quantize="fp16" if config.INFERENCE_HALF_PRECISION else "fp32",
                verbose=False,
            )
        except Exception as track_err:
            log.warning("Tracking fallback to predict due to tracker error: %s", track_err)
            results = self.model.predict(
                frame,
                conf=config.DETECTION_CONF,
                imgsz=config.INFERENCE_IMG_SIZE,
                verbose=False,
            )

        if not results:
            return frame, []

        result = results[0]
        boxes  = result.boxes

        raw_persons: list[dict] = []
        ppe_items:   list[dict] = []

        if boxes is not None:
            for i in range(len(boxes)):
                cls_id     = int(boxes.cls[i].item())
                class_name = self.model.names.get(cls_id, f"cls_{cls_id}")
                box        = boxes.xyxy[i].tolist()
                conf       = float(boxes.conf[i].item())

                if class_name.lower() in ("person", "worker", "human"):
                    raw_id = None
                    if boxes.id is not None and i < len(boxes.id) and boxes.id[i] is not None:
                        try:
                            val = float(boxes.id[i].item())
                            if not np.isnan(val):
                                raw_id = int(val)
                        except (ValueError, TypeError):
                            raw_id = None

                    raw_persons.append({
                        "raw_id":    raw_id,
                        "box":       box,
                        "class_name": "person",
                        "confidence": conf,
                    })
                elif class_name in ALL_PPE_CLASSES:
                    ppe_items.append({
                        "box":        box,
                        "class_name": class_name,
                        "confidence": conf,
                    })

        # 1. Non-Maximum Suppression for person bounding boxes (eliminates duplicate stacked boxes on 1 person)
        def _suppress_overlapping_persons(p_list: list[dict], iou_thresh: float = 0.45) -> list[dict]:
            if not p_list:
                return []
            sorted_p = sorted(p_list, key=lambda x: x.get("confidence", 0.0), reverse=True)
            keep: list[dict] = []
            for p in sorted_p:
                box_p = p["box"]
                should_keep = True
                for k in keep:
                    box_k = k["box"]
                    if self._compute_walk_robust_similarity(box_p, box_k) >= iou_thresh:
                        should_keep = False
                        break
                if should_keep:
                    keep.append(p)
            return keep

        # 2. Fallback: If no person box detected by YOLO, synthesize ONE merged container enclosing all PPE items
        if not raw_persons and ppe_items:
            min_x1 = min(p["box"][0] for p in ppe_items)
            min_y1 = min(p["box"][1] for p in ppe_items)
            max_x2 = max(p["box"][2] for p in ppe_items)
            max_y2 = max(p["box"][3] for p in ppe_items)
            mean_conf = float(np.mean([p["confidence"] for p in ppe_items]))
            
            w_box = [
                max(0, min_x1 - 40),
                max(0, min_y1 - 30),
                max_x2 + 40,
                max_y2 + 160
            ]
            raw_persons.append({
                "raw_id": None,
                "box": w_box,
                "class_name": "person",
                "confidence": mean_conf,
            })
        else:
            raw_persons = _suppress_overlapping_persons(raw_persons, iou_thresh=0.45)

        # ── Walk-Robust Spatial Track Memory Matching (handles scale changes & occlusion) ──
        persons: list[dict] = []
        used_memory_ids: set[int] = set()

        for rp in raw_persons:
            box = rp["box"]
            raw_id = rp["raw_id"]
            assigned_id = None

            # 1. Direct raw_id match if existing in tracking memory
            if raw_id is not None and raw_id > 0 and raw_id in self._track_memory and raw_id not in used_memory_ids:
                assigned_id = raw_id
            else:
                # 2. Match against active track memory using walk-robust similarity
                best_sim = 0.0
                best_id = None
                for mem_id, mem_data in self._track_memory.items():
                    if mem_id in used_memory_ids:
                        continue
                    sim = self._compute_walk_robust_similarity(box, mem_data["box"])
                    if sim > best_sim:
                        best_sim = sim
                        best_id = mem_id

                if best_sim >= 0.18 and best_id is not None:
                    assigned_id = best_id
                elif raw_id is not None and raw_id > 0 and raw_id not in used_memory_ids:
                    assigned_id = raw_id
                else:
                    assigned_id = self._next_synthetic_id
                    self._next_synthetic_id += 1

            used_memory_ids.add(assigned_id)
            self._track_memory[assigned_id] = {
                "box": box,
                "last_frame": self._frame_count,
            }

            persons.append({
                "id":         assigned_id,
                "box":        box,
                "class_name": "person",
                "confidence": rp["confidence"],
            })

        # Clean stale tracking memory older than 90 frames (~4.5 seconds)
        stale_ids = [
            tid for tid, tdata in self._track_memory.items()
            if self._frame_count - tdata["last_frame"] > 90
        ]
        for tid in stale_ids:
            del self._track_memory[tid]

        # ── Stage 3: person-to-PPE association ────────────────────────────────
        person_ppe_map = associate_ppe_to_persons(persons, ppe_items)

        # ── Stage 4+5: rule engine + worker tracker + temporal validation ─────
        # Get zone requirements for active zone
        zone_cfg = self._rule_engine.get_zone(active_zone)
        required_ppe = zone_cfg.required_ppe if zone_cfg else {"helmet", "vest"}

        worker_states: list[dict] = []
        for person in persons:
            pid  = person["id"]
            ppes = person_ppe_map.get(pid, [])

            raw_detected = {p["class_name"] for p in ppes}
            mean_conf    = (
                float(np.mean([p["confidence"] for p in ppes]))
                if ppes else 0.0
            )

            # ── Worker tracker: majority voting across frames ─────────────
            smoothed_detected, smoothed_missing = self._worker_tracker.update(
                worker_id=pid,
                raw_detected=raw_detected,
                required_ppe=required_ppe,
            )

            compliant = len(smoothed_missing) == 0

            # Evaluate rule engine
            compliance = self._rule_engine.evaluate(
                worker_id=pid,
                detected_ppe=smoothed_detected,
                zone=active_zone,
                confidence=mean_conf,
            )

            # Stage 5: Temporal validation — only fire alert after sustained violation
            temporal_alert, temporal_reason = self._temporal_validator.update(compliance)

            with self._lock:
                mqtt_alert = self._publisher.process_compliance_result(compliance)

            is_new_alert = temporal_alert  # Gated by temporal validation, not single-frame

            worker_states.append({
                "worker_id":   f"Worker-{pid}",
                "zone":        active_zone,
                "detected_ppe":sorted(smoothed_detected),
                "missing_ppe": sorted(smoothed_missing),
                "required_ppe":sorted(required_ppe),
                "compliant":   compliant,
                "confidence":  round(mean_conf, 3),
                "is_new_alert": is_new_alert,
            })

            # Draw annotations using smoothed state
            self._draw_person(frame, person, compliant,
                              smoothed_missing, ppes)

        # Draw PPE item boxes
        for ppe in ppe_items:
            self._draw_ppe(frame, ppe)

        # Save last detection caches for adaptive frame skipping
        self._last_worker_states = worker_states
        self._last_persons = persons
        self._last_ppe_items = ppe_items

        # Cleanup workers that have left the scene
        self._worker_tracker.cleanup_stale()

        return frame, worker_states

    def release(self) -> None:
        self._publisher.close()

    # ── Drawing helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _draw_person(
        frame:       np.ndarray,
        person:      dict,
        compliant:   bool,
        missing_ppe: set[str],
        ppes:        list[dict],
    ) -> None:
        x1, y1, x2, y2 = map(int, person["box"])
        colour = COMPLIANCE_COLOURS[compliant]
        cv2.rectangle(frame, (x1, y1), (x2, y2), colour, 2)

        label = f"Worker-{person['id']}"
        if compliant:
            status = "COMPLIANT"
        else:
            status = "MISSING: " + ", ".join(sorted(missing_ppe))

        cv2.putText(frame, label,  (x1, y1 - 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, colour, 2)
        cv2.putText(frame, status, (x1, y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, colour, 1)

    @staticmethod
    def _draw_ppe(frame: np.ndarray, ppe: dict) -> None:
        x1, y1, x2, y2 = map(int, ppe["box"])
        cv2.rectangle(frame, (x1, y1), (x2, y2), (200, 150, 0), 1)
        cv2.putText(
            frame,
            f"{ppe['class_name']} {ppe['confidence']:.2f}",
            (x1, y1 - 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 150, 0), 1,
        )


# ── CLI demo ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    source = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() \
             else (sys.argv[1] if len(sys.argv) > 1 else 0)
    zone   = sys.argv[2] if len(sys.argv) > 2 else config.DEFAULT_ZONE

    detector = PPEDetector(zone=zone)
    cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        print(f"Cannot open source: {source}")
        sys.exit(1)

    print(f"Running detector. Zone: {zone}. Press 'q' to quit.")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        annotated, states = detector.process_frame(frame, zone=zone)
        cv2.imshow("PPE Detector", annotated)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    detector.release()
