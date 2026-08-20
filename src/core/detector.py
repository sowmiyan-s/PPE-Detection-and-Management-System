"""
Stage 1 + 2 + 3 – Person detection & tracking, PPE detection, and association.

Combines YOLOv8 ByteTrack (Stage 1), multi-class PPE detection (Stage 2),
body-region-aware association (Stage 3), zone rule evaluation (Stage 4), and
temporal validation (Stage 5) via PPEMqttPublisher.
"""

from __future__ import annotations

import logging
import math
import os
import threading
from typing import Optional

import cv2
import numpy as np

# PyTorch 2.6+ compatibility & Windows multiprocessing safety
try:
    import torch
    _orig_torch_load = getattr(torch, "load", None)
    if _orig_torch_load:
        def _safe_torch_load(f, *args, **kwargs):
            kwargs.setdefault("weights_only", False)
            return _orig_torch_load(f, *args, **kwargs)
        torch.load = _safe_torch_load

    if hasattr(torch, "cuda") and not torch.cuda.is_available():
        num_cpus = os.cpu_count() or 4
        torch.set_num_threads(max(1, num_cpus - 1))
except Exception as _torch_err:
    logging.warning("PyTorch initialization note: %s", _torch_err)


from ultralytics import YOLO

from src.core import config
from src.core import runtime
from src.core.association import associate_ppe_to_persons
from src.core.publisher import PPEMqttPublisher
from src.core.rule_engine import RuleEngine
from src.core.worker_tracker import WorkerTracker, POSITIVE_PPE, WorkerReIDGallery
from src.core.temporal_validator import TemporalValidator

log = logging.getLogger(__name__)

def _run_model_track(model, frame, **kwargs):
    return model.track(frame, **kwargs)

def _run_model_predict(model, frame, **kwargs):
    return model.predict(frame, **kwargs)

# ── Class definitions (must match data.yaml) ────────────────────────────────

ALL_PPE_CLASSES: set[str] = {
    # Full models/best.pt model class set (19 classes)
    "Boots", "Ear-Protection", "Glass", "Glove", "Hard_hat", "Mask",
    "No-Boots", "No-Ear-Protection", "No-Glass", "No-Glove", "No-Helmet", "No-Mask", "No-Vest",
    "Worker", "Vest", "Circular_Saw", "Fire_Extinguisher", "Fire_prevention_Net", "Welding_Equipment",
    # Canonical normalized keys
    "person", "worker", "helmet", "vest", "boots", "gloves", "glasses", "mask", "earmuffs", "glove", "glass", "ear_protection"
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
        if model_path is None:
            model_path = config.DEFAULT_MODEL_PATH

        def _is_invalid_or_lfs(path: str) -> bool:
            if not path or not os.path.exists(path):
                return True
            if os.path.getsize(path) < 1024:
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        if "git-lfs" in f.read(100):
                            return True
                except Exception:
                    pass
            return False

        if _is_invalid_or_lfs(model_path):
            log.warning("Custom model invalid or LFS pointer at %s, using fallback %s",
                        model_path, config.FALLBACK_MODEL_PATH)
            model_path = config.FALLBACK_MODEL_PATH

        if _is_invalid_or_lfs(model_path):
            model_path = "models/best.pt"

        # Jetson / TensorRT auto-fallback: if we requested a .pt but a .engine exists, use it.
        engine_path = model_path.replace('.pt', '.engine')
        if os.path.exists(engine_path):
            log.info("Found TensorRT engine at %s, preferring it for max performance.", engine_path)
            model_path = engine_path

        try:
            self.model = YOLO(model_path)
        except Exception as load_err:
            log.warning("Failed to load model %s (%s), loading models/best.pt", model_path, load_err)
            self.model = YOLO("models/best.pt")
        self.default_zone = zone

        # Dynamically register all model non-person class names into ALL_PPE_CLASSES
        if hasattr(self.model, "names") and isinstance(self.model.names, dict):
            for c_name in self.model.names.values():
                if str(c_name).lower() not in ("person", "worker", "human"):
                    ALL_PPE_CLASSES.add(c_name)

        # ── Supporting components ───────────────────────────────────────────────
        self._publisher = PPEMqttPublisher(broker=broker, port=port, topic=topic)
        self._rule_engine = RuleEngine()
        self._worker_tracker = WorkerTracker()
        self._reid_gallery = WorkerReIDGallery(ttl_seconds=1800.0, match_threshold=0.65)
        self._temporal_validator = TemporalValidator()
        self._lock = threading.Lock()
        
        # Register all initial zone rules in temporal validator
        for z_name, z_cfg in self._rule_engine._zones.items():
            self._temporal_validator.set_zone_thresholds(
                zone_name=z_name,
                min_hits=z_cfg.frame_threshold,
                min_zone_secs=z_cfg.dwell_seconds,
                min_conf=z_cfg.confidence,
            )
        
        self._track_memory: dict[int, dict] = {}  # track_id -> {"box": list, "last_frame": int}
        self._frame_count: int = 0
        self._next_synthetic_id: int = 1

        # Adaptive frame-skip cache for low-end CPU systems
        self._last_worker_states: list[dict] = []
        self._last_persons: list[dict] = []
        self._last_ppe_items: list[dict] = []

    def update_zone_rule(
        self,
        zone_name: str,
        required_ppe: set[str],
        frame_threshold: int = 8,
        dwell_seconds: int = 2,
        confidence: float = 0.60,
    ) -> None:
        """Update required PPE rules and temporal parameters for a zone at runtime."""
        with self._lock:
            self._rule_engine.add_zone(
                name=zone_name,
                required_ppe=required_ppe,
                frame_threshold=frame_threshold,
                dwell_seconds=dwell_seconds,
                confidence=confidence,
            )
            config.ZONE_RULES[zone_name] = required_ppe
            self._temporal_validator.set_zone_thresholds(
                zone_name=zone_name,
                min_hits=frame_threshold,
                min_zone_secs=float(dwell_seconds),
                min_conf=float(confidence),
            )
            log.info(
                "PPEDetector updated zone '%s' rules to: %s (frames=%d, dwell=%ds, conf=%.2f)",
                zone_name, required_ppe, frame_threshold, dwell_seconds, confidence
            )

    def update_zone_config(
        self,
        zone_name: str,
        required_ppe: set[str],
        frame_threshold: int = 8,
        dwell_seconds: int = 2,
        confidence: float = 0.60,
    ) -> None:
        """Convenience alias for update_zone_rule."""
        self.update_zone_rule(zone_name, required_ppe, frame_threshold, dwell_seconds, confidence)

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
        is_single_image: bool = False,
        is_testing: bool = False,
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
        zone_cfg = self._rule_engine.get_zone(active_zone)
        required_ppe = zone_cfg.required_ppe if zone_cfg else config.ZONE_RULES.get(active_zone, set())
        aliases = getattr(config, "PPE_ALIASES", {})

        # Low-end CPU adaptive frame skip check: reuse cached detections on skipped frames
        if config.FRAME_SKIP_INTERVAL > 0 and (self._frame_count % (config.FRAME_SKIP_INTERVAL + 1) != 0) and self._last_worker_states:
            for person in self._last_persons:
                compliant = next((w["compliant"] for w in self._last_worker_states if w.get("worker_id") == f"Worker-{person['id']}"), True)
                missing = next((set(w.get("missing_ppe", [])) for w in self._last_worker_states if w.get("worker_id") == f"Worker-{person['id']}"), set())
                ppes = person.get("ppes", [])
                self._draw_person(frame, person, compliant, missing, ppes, required_ppe=required_ppe, is_testing=is_testing)
            for ppe in self._last_ppe_items:
                self._draw_ppe(frame, ppe)
            return frame, self._last_worker_states

        # ── Stage 1+2: detect + track (raw frame — no enhancer for speed) ────
        # imgsz & device are derived adaptively (runtime.py) so multi-camera
        # GPU load stays bounded and every stream keeps a usable FPS.
        infer_imgsz = runtime.get_adaptive_img_size()
        use_half = config.INFERENCE_HALF_PRECISION and str(runtime.INFERENCE_DEVICE) != "cpu"
        try:
            infer_kwargs = {
                "conf": config.DETECTION_CONF,
                "imgsz": infer_imgsz,
                "device": runtime.INFERENCE_DEVICE,
                "verbose": False,
            }
            if use_half:
                infer_kwargs["quantize"] = "fp16"

            results = _run_model_track(
                self.model,
                frame,
                persist=True,
                tracker=config.TRACKER_CONFIG,
                **infer_kwargs
            )
        except Exception as track_err:
            log.warning("Tracking fallback to predict due to tracker error: %s", track_err)
            results = _run_model_predict(
                self.model,
                frame,
                **infer_kwargs
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

                if not box or len(box) < 4 or any(math.isnan(float(x)) or math.isinf(float(x)) for x in box[:4]):
                    continue

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

        # ── Motion-Aware Spatial & Appearance Track Memory Matching ─────────────
        persons: list[dict] = []
        used_memory_ids: set[int] = set()
        matched_detections: set[int] = set()

        # Step 1: Pre-extract visual signatures for current detections
        det_sigs = [
            self._reid_gallery.extract_signature(frame, rp["box"])
            for rp in raw_persons
        ]

        # Step 2: Score all candidate pairs between detections & active tracklets
        match_candidates = []
        for d_idx, rp in enumerate(raw_persons):
            box = rp["box"]
            raw_id = rp.get("raw_id")
            sig = det_sigs[d_idx]
            
            for mem_id, mem_data in self._track_memory.items():
                age = self._frame_count - mem_data.get("last_frame", 0)
                if age > 120:  # 6 seconds at 20fps
                    continue
                
                # Spatial similarity with motion prediction
                mem_box = mem_data["box"]
                vx = mem_data.get("vx", 0.0)
                vy = mem_data.get("vy", 0.0)
                pred_box = [
                    mem_box[0] + vx * age,
                    mem_box[1] + vy * age,
                    mem_box[2] + vx * age,
                    mem_box[3] + vy * age
                ]
                
                s_curr = self._compute_walk_robust_similarity(box, mem_box)
                s_pred = self._compute_walk_robust_similarity(box, pred_box)
                spatial_score = max(s_curr, s_pred)
                
                # Visual appearance color score
                color_score = 0.5
                mem_sig = mem_data.get("sig")
                if sig is not None and mem_sig is not None:
                    color_score = float(np.dot(sig, mem_sig))
                
                # Combined weighted score
                total_score = (0.65 * spatial_score) + (0.35 * max(0.0, color_score))
                
                # Raw ByteTrack ID agreement bonus
                if raw_id is not None and raw_id == mem_id:
                    total_score += 0.30
                
                # Single person in scene stability boost
                if len(raw_persons) == 1 and len(self._track_memory) == 1 and spatial_score >= 0.15:
                    total_score += 0.40
                    
                match_candidates.append({
                    "d_idx": d_idx,
                    "mem_id": mem_id,
                    "score": total_score,
                    "spatial": spatial_score
                })

        # Step 3: Best-first greedy assignment
        match_candidates.sort(key=lambda x: x["score"], reverse=True)
        assigned_map: dict[int, int] = {}

        for c in match_candidates:
            d_idx = c["d_idx"]
            mem_id = c["mem_id"]
            if d_idx in matched_detections or mem_id in used_memory_ids:
                continue
            if c["score"] >= 0.30 or (c["spatial"] >= 0.25):
                assigned_map[d_idx] = mem_id
                matched_detections.add(d_idx)
                used_memory_ids.add(mem_id)

        # Step 4: Finalize assigned IDs & update motion memory
        import time as _t
        now_ts = _t.time()

        for d_idx, rp in enumerate(raw_persons):
            box = rp["box"]
            raw_id = rp.get("raw_id")
            sig = det_sigs[d_idx]
            
            if d_idx in assigned_map:
                final_id = assigned_map[d_idx]
            elif raw_id is not None and raw_id > 0 and raw_id not in used_memory_ids:
                final_id = raw_id
            elif len(raw_persons) == 1 and len(self._track_memory) >= 1:
                # Strong single-worker stability: stick to most recent worker ID
                most_recent_id = max(self._track_memory.keys(), key=lambda k: self._track_memory[k].get("last_frame", 0))
                if (self._frame_count - self._track_memory[most_recent_id].get("last_frame", 0) <= 150) and most_recent_id not in used_memory_ids:
                    final_id = most_recent_id
                else:
                    final_id = self._reid_gallery.match_or_register(self._next_synthetic_id, frame, box, now_ts, exclude_ids=used_memory_ids)
                    if final_id == self._next_synthetic_id:
                        self._next_synthetic_id += 1
            else:
                while self._next_synthetic_id in self._track_memory or self._next_synthetic_id in used_memory_ids:
                    self._next_synthetic_id += 1
                final_id = self._reid_gallery.match_or_register(self._next_synthetic_id, frame, box, now_ts, exclude_ids=used_memory_ids)
                if final_id == self._next_synthetic_id:
                    self._next_synthetic_id += 1

            used_memory_ids.add(final_id)

            # Update motion velocity & appearance signature
            cx = (box[0] + box[2]) / 2.0
            cy = (box[1] + box[3]) / 2.0
            prev = self._track_memory.get(final_id)
            if prev and "cx" in prev:
                dt_frames = max(1, self._frame_count - prev.get("last_frame", self._frame_count))
                vx = 0.6 * ((cx - prev["cx"]) / dt_frames) + 0.4 * prev.get("vx", 0.0)
                vy = 0.6 * ((cy - prev["cy"]) / dt_frames) + 0.4 * prev.get("vy", 0.0)
            else:
                vx, vy = 0.0, 0.0

            old_sig = prev.get("sig") if prev else None
            if sig is not None and old_sig is not None:
                updated_sig = 0.85 * old_sig + 0.15 * sig
                norm_val = np.linalg.norm(updated_sig)
                if norm_val > 1e-6: updated_sig /= norm_val
            else:
                updated_sig = sig

            self._track_memory[final_id] = {
                "box": box,
                "cx": cx,
                "cy": cy,
                "vx": vx,
                "vy": vy,
                "sig": updated_sig,
                "last_frame": self._frame_count,
            }

            persons.append({
                "id":         final_id,
                "box":        box,
                "class_name": "person",
                "confidence": rp["confidence"],
            })

        # Clean stale tracking memory older than 300 frames (~15 seconds)
        stale_ids = [
            tid for tid, tdata in self._track_memory.items()
            if self._frame_count - tdata["last_frame"] > 300
        ]
        for tid in stale_ids:
            del self._track_memory[tid]

        # Strict Turned-ON Feature Filtering: Only retain detections for PPE labels turned ON for active zone unless in testing mode
        def _is_turned_on(cls_name: str) -> bool:
            if is_testing:
                return True
            c_str = str(cls_name).strip()
            c_lower = c_str.lower()
            canonical_key = aliases.get(c_str, c_lower.replace("no-", "").replace("no_", "").strip())
            return canonical_key in required_ppe or c_lower in required_ppe

        active_ppe_items = [p for p in ppe_items if _is_turned_on(p["class_name"])]

        # ── Stage 3: person-to-PPE association ─────────────
        person_ppe_map = associate_ppe_to_persons(persons, active_ppe_items)

        worker_states: list[dict] = []
        for person in persons:
            pid  = person["id"]
            pbox = person["box"]
            cx   = (pbox[0] + pbox[2]) / 2.0
            cy   = (pbox[1] + pbox[3]) / 2.0
            ppes = person_ppe_map.get(pid, [])

            raw_detected = {p["class_name"] for p in ppes}
            mean_conf    = (
                float(np.mean([p["confidence"] for p in ppes]))
                if ppes else 0.0
            )

            # ── Worker tracker: majority voting + state machine ─────────────
            smoothed_detected, smoothed_missing = self._worker_tracker.update(
                worker_id=pid,
                raw_detected=raw_detected,
                required_ppe=required_ppe,
                is_single_image=is_single_image,
            )

            compliant = len(smoothed_missing) == 0

            # Evaluate rule engine
            compliance = self._rule_engine.evaluate(
                worker_id=pid,
                detected_ppe=smoothed_detected,
                zone=active_zone,
                confidence=mean_conf,
            )

            # Stage 5: Temporal validation + spatial debouncing — fire alert after sustained violation
            temporal_alert, temporal_reason = self._temporal_validator.update(compliance, bbox_center=(cx, cy))

            with self._lock:
                try:
                    mqtt_alert = self._publisher.process_compliance_result(compliance, bbox_center=(cx, cy))
                except Exception as pub_err:
                    log.warning("MQTT publishing error: %s", pub_err)
                    mqtt_alert = None

            is_new_alert = temporal_alert  # Gated by temporal validation, not single-frame
            person["ppes"] = ppes

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

            # Draw annotations using smoothed state & zone required PPE rules
            self._draw_person(frame, person, compliant,
                              smoothed_missing, ppes, required_ppe=required_ppe, is_testing=is_testing)

        # Draw standalone equipment (e.g. Circular_Saw, Fire_Extinguisher) when in testing mode
        if is_testing:
            equip_items = [p for p in ppe_items if p["class_name"] in ("Circular_Saw", "Fire_Extinguisher", "Fire_prevention_Net", "Welding_Equipment")]
            for eq in equip_items:
                ex1, ey1, ex2, ey2 = map(int, eq["box"])
                eq_name = eq["class_name"].replace("_", " ").upper()
                cv2.rectangle(frame, (ex1, ey1), (ex2, ey2), (255, 200, 0), 2)
                PPEDetector._draw_badge(frame, f"EQUIPMENT: {eq_name}", (ex1, max(18, ey1)), (220, 160, 0), scale=0.42)

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
    def _draw_badge(
        frame:      np.ndarray,
        text:       str,
        pos:        tuple[int, int],
        bg_color:   tuple[int, int, int] = (0, 180, 0),
        text_color: tuple[int, int, int] = (255, 255, 255),
        scale:      float = 0.42,
    ) -> None:
        x, y = pos
        font = cv2.FONT_HERSHEY_SIMPLEX
        thick = 1
        (w, h), baseline = cv2.getTextSize(text, font, scale, thick)
        pad = 2
        bg_y1 = max(0, y - h - pad * 2)
        bg_y2 = y + pad * 2
        cv2.rectangle(frame, (x, bg_y1), (x + w + pad * 4, bg_y2), bg_color, -1)
        cv2.putText(
            frame,
            text,
            (x + pad * 2, max(12, y)),
            font,
            scale,
            text_color,
            thick,
            lineType=cv2.LINE_AA
        )

    @staticmethod
    def _draw_person(
        frame:       np.ndarray,
        person:      dict,
        compliant:   bool,
        missing_ppe: set[str],
        ppes:        list[dict],
        required_ppe: Optional[set[str]] = None,
        is_testing:  bool = False,
    ) -> None:
        p_box = person.get("box")
        if p_box is None or len(p_box) < 4:
            return
        if any(math.isnan(float(b)) or math.isinf(float(b)) for b in p_box[:4]):
            return
        x1, y1, x2, y2 = map(int, p_box[:4])
        w_id = person.get("id", 1)
        req_set = required_ppe or set()
        aliases = getattr(config, "PPE_ALIASES", {})

        if compliant:
            # Draw GREEN box & banner for COMPLIANT worker with met constraints
            colour = (0, 200, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), colour, 2)
            banner_y1 = max(0, y1 - 24) if y1 >= 24 else y1
            banner_y2 = y1 if y1 >= 24 else y1 + 24
            cv2.rectangle(frame, (x1, banner_y1), (x2, banner_y2), colour, -1)
            cv2.putText(frame, f"WORKER-{w_id} | COMPLIANT", (x1 + 6, max(14, banner_y2 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 2, cv2.LINE_AA)
        else:
            # Draw RED box & header banner for NON-COMPLIANT worker
            colour = (0, 0, 220)
            cv2.rectangle(frame, (x1, y1), (x2, y2), colour, 3)

            missing_str = ", ".join(sorted(missing_ppe)).upper().replace("_", " ")
            label1 = f"WORKER-{w_id} | MISSING PPE"
            label2 = f"MISSING: {missing_str}"

            banner_y1 = max(0, y1 - 36) if y1 >= 36 else y1
            banner_y2 = y1 if y1 >= 36 else y1 + 36
            cv2.rectangle(frame, (x1, banner_y1), (x2, banner_y2), colour, -1)
            cv2.putText(frame, label1, (x1 + 6, max(14, banner_y2 - 20)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(frame, label2, (x1 + 6, max(28, banner_y2 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 255, 255), 1, cv2.LINE_AA)

        # Deduplicate and resolve conflicts among associated PPE boxes on this worker
        def _resolve_ppe_conflicts(item_list: list[dict]) -> list[dict]:
            if not item_list:
                return []
            by_type: dict[str, list[dict]] = {}
            for p in item_list:
                c_name = p.get("class_name", "")
                c_lower = c_name.lower()
                base_type = aliases.get(c_name, c_lower.replace("no-", "").replace("no_", "").strip())
                by_type.setdefault(base_type, []).append(p)

            resolved: list[dict] = []
            for base_type, items in by_type.items():
                def _is_neg(c: str) -> bool:
                    c_lower = str(c).lower()
                    return c_lower.startswith("no") or c_lower == "lanyard_bad"

                positives = [it for it in items if not _is_neg(it["class_name"])]
                negatives = [it for it in items if _is_neg(it["class_name"])]

                if positives and negatives:
                    best_pos = max(positives, key=lambda x: x.get("confidence", 0.0))
                    best_neg = max(negatives, key=lambda x: x.get("confidence", 0.0))
                    if best_pos["confidence"] >= best_neg["confidence"]:
                        resolved.append(best_pos)
                    else:
                        resolved.append(best_neg)
                elif positives:
                    resolved.append(max(positives, key=lambda x: x.get("confidence", 0.0)))
                elif negatives:
                    resolved.append(max(negatives, key=lambda x: x.get("confidence", 0.0)))
                else:
                    resolved.append(items[0])

            return resolved

        clean_ppes = _resolve_ppe_conflicts(ppes)

        # Draw associated PPE item boxes without badge collisions
        for ppe in clean_ppes:
            px1, py1, px2, py2 = map(int, ppe["box"])
            c_name = ppe.get("class_name", "")
            c_lower = c_name.lower()
            norm_name = c_name.replace("No-", "").replace("no-", "").replace("no_", "").replace("_", " ").upper()
            canonical_key = aliases.get(c_name, c_lower.replace("no-", "").replace("no_", "").strip())

            # Anti-collision badge positioning: if py1 is near worker header y1, position badge inside box
            if abs(py1 - y1) < 40 or py1 < 25:
                badge_pos = (px1 + 2, min(py2 - 4, py1 + 18))
            else:
                badge_pos = (px1, py1)

            if c_lower.startswith("no") or c_lower == "lanyard_bad":
                # Draw missing constraint box (unless live mode and item not in required set)
                if not is_testing and req_set and canonical_key not in req_set and norm_name.lower() not in req_set:
                    continue
                cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 0, 220), 2)
                PPEDetector._draw_badge(frame, f"MISSING: {norm_name}", badge_pos, (0, 0, 220), scale=0.42)
            else:
                # Found constraint box -> GREEN
                cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 180, 0), 2)
                PPEDetector._draw_badge(frame, f"OK: {norm_name}", badge_pos, (0, 160, 0), scale=0.42)

    @staticmethod
    def _draw_ppe(frame: np.ndarray, ppe: dict) -> None:
        box = ppe.get("box")
        if not box or len(box) < 4:
            return
        px1, py1, px2, py2 = map(int, box[:4])
        c_name = ppe.get("class_name", "")
        c_lower = c_name.lower()
        norm_name = c_name.replace("No-", "").replace("no-", "").replace("no_", "").replace("_", " ").upper()

        if c_lower.startswith("no") or c_lower == "lanyard_bad":
            cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 0, 220), 2)
            PPEDetector._draw_badge(frame, f"MISSING: {norm_name}", (px1, max(18, py1)), (0, 0, 220), scale=0.42)
        else:
            cv2.rectangle(frame, (px1, py1), (px2, py2), (0, 180, 0), 2)
            PPEDetector._draw_badge(frame, f"OK: {norm_name}", (px1, max(18, py1)), (0, 160, 0), scale=0.42)


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
