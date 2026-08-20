"""
Full vision pipeline — wraps Stage 1-5 for use by server.py and other callers.

The pipeline is intentionally thin: it delegates all heavy lifting to
PPEDetector (which owns the model, enhancer, rule engine, publisher, and
temporal validator).  server.py creates one VisionPipeline, feeds frames
to it in a loop, and streams the annotated output + worker state via
WebSocket.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from src.core import config
from src.core.detector import PPEDetector

log = logging.getLogger(__name__)


class VisionPipeline:
    """
    Convenience wrapper used by server.py and any other caller that wants
    frame-level inference without constructing PPEDetector directly.

    Parameters
    ----------
    model_path  : path to YOLO weights (.pt or .engine)
    zone        : active safety zone name (matches config.ZONE_RULES keys)
    ppe_classes : unused (kept for API compatibility with original code)
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        zone:       str           = config.DEFAULT_ZONE,
        ppe_classes: Optional[list] = None,   # backward-compat, not used
    ) -> None:
        self._detector = PPEDetector(model_path=model_path, zone=zone)
        self.zone = zone

    # ── Public API ─────────────────────────────────────────────────────────────

    def process_frame(
        self,
        frame: np.ndarray,
        zone:  Optional[str] = None,
    ) -> tuple[np.ndarray, list[dict]]:
        """
        Run the full 5-stage pipeline on one BGR frame.

        Returns
        -------
        annotated_frame : BGR ndarray with bounding-box overlays
        worker_states   : list of per-worker compliance dicts, e.g.
            [{"worker_id": "Worker-101", "zone": "construction",
              "detected_ppe": ["helmet", "vest"],
              "missing_ppe": ["boots"],
              "compliant": False,
              "confidence": 0.76}]
        """
        return self._detector.process_frame(frame, zone=zone or self.zone)

    def set_zone(self, zone: str) -> None:
        """Switch the active safety zone at runtime."""
        self.zone = zone
        self._detector.default_zone = zone

    def update_zone_rule(
        self,
        zone_name: str,
        required_ppe: set[str],
        frame_threshold: int = 8,
        dwell_seconds: int = 2,
        confidence: float = 0.60,
    ) -> None:
        """Proxy runtime zone rule update to PPEDetector."""
        self._detector.update_zone_rule(
            zone_name=zone_name,
            required_ppe=required_ppe,
            frame_threshold=frame_threshold,
            dwell_seconds=dwell_seconds,
            confidence=confidence,
        )

    def update_zone_config(
        self,
        zone_name: str,
        required_ppe: set[str],
        frame_threshold: int = 8,
        dwell_seconds: int = 2,
        confidence: float = 0.60,
    ) -> None:
        """Proxy runtime zone rule & temporal thresholds update."""
        self.update_zone_rule(
            zone_name=zone_name,
            required_ppe=required_ppe,
            frame_threshold=frame_threshold,
            dwell_seconds=dwell_seconds,
            confidence=confidence,
        )

    def release(self) -> None:
        self._detector.release()
