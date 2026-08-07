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
from src.core.enhancer import IndustrialImageEnhancer
from src.core.publisher import PPEMqttPublisher
from src.core.rule_engine import RuleEngine

log = logging.getLogger(__name__)

# ── Class definitions (must match dataset.yaml) ────────────────────────────────

ALL_PPE_CLASSES: set[str] = {
    "helmet", "vest", "boots", "safety_belt", "lanyard", "hook", "anchor_point"
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

        self.model       = YOLO(model_path)
        self.default_zone = zone

        # ── Supporting components ───────────────────────────────────────────────
        self._enhancer  = IndustrialImageEnhancer()
        self._publisher = PPEMqttPublisher(broker=broker, port=port, topic=topic)
        self._rule_engine = RuleEngine()
        self._lock = threading.Lock()

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
        active_zone = zone or self.default_zone
        enhanced    = self._enhancer.enhance(frame)

        # ── Stage 1+2: detect + track ───────────────────────────────────────
        results = self.model.track(
            enhanced,
            persist=True,
            tracker=config.TRACKER_CONFIG,
            conf=config.DETECTION_CONF,
            verbose=False,
        )

        if not results:
            return frame, []

        result = results[0]
        boxes  = result.boxes

        persons:   list[dict] = []
        ppe_items: list[dict] = []

        if boxes is not None:
            for i in range(len(boxes)):
                cls_id     = int(boxes.cls[i].item())
                class_name = self.model.names.get(cls_id, f"cls_{cls_id}")
                box        = boxes.xyxy[i].tolist()
                conf       = float(boxes.conf[i].item())

                if class_name in ("person", "worker", "human"):
                    track_id = (
                        int(boxes.id[i].item())
                        if (boxes.id is not None and i < len(boxes.id) and boxes.id[i] is not None)
                        else (i + 101)
                    )
                    persons.append({
                        "id":         track_id,
                        "box":        box,
                        "class_name": "person",
                        "confidence": conf,
                    })
                elif class_name in ALL_PPE_CLASSES:
                    # Enforce strict 0.60 minimum confidence for helmets
                    if class_name == "helmet" and conf < 0.60:
                        continue
                        
                    ppe_items.append({
                        "box":        box,
                        "class_name": class_name,
                        "confidence": conf,
                    })

        # Fallback: If PPE items exist but no person box was tracked, synthesize worker person container
        if not persons and ppe_items:
            for idx, ppe in enumerate(ppe_items):
                px1, py1, px2, py2 = ppe["box"]
                # Expand box vertically & horizontally to represent worker area
                w_box = [max(0, px1 - 30), max(0, py1 - 20), px2 + 30, py2 + 150]
                persons.append({
                    "id": 101 + idx,
                    "box": w_box,
                    "class_name": "person",
                    "confidence": ppe["confidence"],
                })

        # ── Stage 3: person-to-PPE association ────────────────────────────────
        person_ppe_map = associate_ppe_to_persons(persons, ppe_items)

        # ── Stage 4+5: rule engine + temporal validation ──────────────────────
        worker_states: list[dict] = []
        for person in persons:
            pid  = person["id"]
            ppes = person_ppe_map.get(pid, [])

            detected_set = {p["class_name"] for p in ppes}
            mean_conf    = (
                float(np.mean([p["confidence"] for p in ppes]))
                if ppes else 0.0
            )

            compliance = self._rule_engine.evaluate(
                worker_id=pid,
                detected_ppe=detected_set,
                zone=active_zone,
                confidence=mean_conf,
            )

            with self._lock:
                is_new_alert = self._publisher.process_compliance_result(compliance)

            worker_states.append({
                "worker_id":   f"Worker-{pid}",
                "zone":        active_zone,
                "detected_ppe":sorted(detected_set),
                "missing_ppe": sorted(compliance.missing_ppe),
                "compliant":   compliance.compliant,
                "confidence":  round(mean_conf, 3),
                "is_new_alert": is_new_alert,
            })

            # Draw annotations
            self._draw_person(frame, person, compliance.compliant,
                              compliance.missing_ppe, ppes)

        # Draw PPE boxes without person
        for ppe in ppe_items:
            self._draw_ppe(frame, ppe)

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
