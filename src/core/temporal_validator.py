"""
Stage 5 – Temporal validation.

Prevents spurious alerts from single uncertain frames.

Alert rule (configurable via config.py):
  • Violation must appear in ≥ TEMPORAL_MIN_HITS of the last TEMPORAL_WINDOW frames
  • Confidence must be ≥ TEMPORAL_MIN_CONF
  • Worker must have been in the zone for ≥ TEMPORAL_MIN_ZONE_SECS seconds

Once an alert fires, it is suppressed until the worker becomes compliant,
preventing repeated alerts for the same continuing violation.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from src.core import config
from src.core.rule_engine import ComplianceResult


@dataclass
class _WorkerState:
    # Sliding window: True = violation frame, False = compliant frame
    frame_window: deque = field(default_factory=lambda: deque(maxlen=config.TEMPORAL_WINDOW))
    zone_entry_time: Optional[float] = None
    last_missing_ppe: set[str] = field(default_factory=set)
    alert_active: bool = False          # True while the same violation is ongoing
    total_violations: int = 0
    total_alerts_fired: int = 0


class TemporalValidator:
    """
    Maintains per-worker sliding-window state and spatial-temporal event debouncing.

    Usage
    -----
    validator = TemporalValidator()
    should_alert, reason = validator.update(result, bbox_center=(cx, cy))
    """

    SPATIAL_COOLDOWN_SECS: float = 12.0  # Cooldown window for localized event suppression
    SPATIAL_RADIUS_PX: float = 180.0     # Radius in frame pixels to group duplicate alerts

    def __init__(self) -> None:
        self._workers: dict[int, _WorkerState] = {}
        self._recent_spatial_alerts: list[dict] = []  # active spatial events list
        self._zone_thresholds: dict[str, dict] = {}

    def set_zone_thresholds(
        self,
        zone_name: str,
        min_hits: Optional[int] = None,
        min_zone_secs: Optional[float] = None,
        min_conf: Optional[float] = None,
    ) -> None:
        """Configure dynamic per-zone temporal noise suppression thresholds."""
        if not zone_name:
            return
        if zone_name not in self._zone_thresholds:
            self._zone_thresholds[zone_name] = {}
        if min_hits is not None:
            self._zone_thresholds[zone_name]["min_hits"] = int(min_hits)
        if min_zone_secs is not None:
            self._zone_thresholds[zone_name]["min_zone_secs"] = float(min_zone_secs)
        if min_conf is not None:
            self._zone_thresholds[zone_name]["min_conf"] = float(min_conf)

    # ── Public API ─────────────────────────────────────────────────────────────

    def update(
        self,
        result: ComplianceResult,
        bbox_center: Optional[tuple[float, float]] = None
    ) -> tuple[bool, str]:
        """
        Feed one compliance result for one worker.

        Parameters
        ----------
        result      – ComplianceResult object
        bbox_center – Optional (cx, cy) bounding box center for spatial debouncing

        Returns
        -------
        (should_alert, reason)
        """
        state = self._get_or_create(result.worker_id)
        now   = time.monotonic()

        # Dynamic per-zone temporal thresholds with global fallbacks
        zone_th = self._zone_thresholds.get(result.zone, {})
        req_min_hits = zone_th.get("min_hits", config.TEMPORAL_MIN_HITS)
        req_min_conf = zone_th.get("min_conf", config.TEMPORAL_MIN_CONF)
        req_min_zone_secs = zone_th.get("min_zone_secs", config.TEMPORAL_MIN_ZONE_SECS)

        # Clean stale spatial events older than SPATIAL_COOLDOWN_SECS
        self._recent_spatial_alerts = [
            ev for ev in self._recent_spatial_alerts
            if (now - ev["timestamp"]) <= self.SPATIAL_COOLDOWN_SECS
        ]

        # Track zone entry time
        if state.zone_entry_time is None:
            state.zone_entry_time = now
        zone_duration = now - state.zone_entry_time

        # Update sliding window
        is_violation = not result.compliant
        state.frame_window.append(is_violation)

        if is_violation:
            state.total_violations += 1

        # Compliant frame clears active alert (so same violation doesn't re-fire)
        if result.compliant:
            if state.alert_active:
                state.alert_active = False
            return False, "compliant"

        # Count violations in window
        hits = sum(state.frame_window)
        window_size = len(state.frame_window)

        if window_size < config.TEMPORAL_WINDOW:
            return False, f"warming up ({window_size}/{config.TEMPORAL_WINDOW} frames)"

        if hits < req_min_hits:
            return False, (
                f"insufficient hits: {hits}/{config.TEMPORAL_WINDOW} "
                f"(need {req_min_hits})"
            )

        if result.confidence < req_min_conf:
            return False, (
                f"confidence too low: {result.confidence:.2f} "
                f"< {req_min_conf}"
            )

        if zone_duration < req_min_zone_secs:
            return False, (
                f"zone duration too short: {zone_duration:.1f}s "
                f"< {req_min_zone_secs}s"
            )

        # All conditions met – suppress if this is the same ongoing worker violation
        if state.alert_active and result.missing_ppe == state.last_missing_ppe:
            return False, "suppressed – same ongoing worker violation"

        # Spatial-Temporal Event Debouncing (Location-Based Suppression)
        if bbox_center is not None:
            cx, cy = bbox_center
            for ev in self._recent_spatial_alerts:
                if (ev["zone"] == result.zone and
                    ev["missing"] == set(result.missing_ppe) and
                    (now - ev["timestamp"]) <= self.SPATIAL_COOLDOWN_SECS):
                    dist = ((cx - ev["cx"]) ** 2 + (cy - ev["cy"]) ** 2) ** 0.5
                    if dist <= self.SPATIAL_RADIUS_PX:
                        state.alert_active = True
                        state.last_missing_ppe = set(result.missing_ppe)
                        return False, f"suppressed – debounced spatial event within {dist:.0f}px"

            # Register new spatial alert event
            self._recent_spatial_alerts.append({
                "zone": result.zone,
                "missing": set(result.missing_ppe),
                "cx": cx,
                "cy": cy,
                "timestamp": now,
            })

        # Fire alert
        state.alert_active     = True
        state.last_missing_ppe = set(result.missing_ppe)
        state.total_alerts_fired += 1
        return True, (
            f"alert: {hits}/{config.TEMPORAL_WINDOW} frames, "
            f"conf={result.confidence:.2f}, zone={zone_duration:.1f}s"
        )

    def reset_worker(self, worker_id: int) -> None:
        """Remove all state for a worker (e.g. when they leave the scene)."""
        self._workers.pop(worker_id, None)

    def get_stats(self, worker_id: int) -> Optional[dict]:
        state = self._workers.get(worker_id)
        if state is None:
            return None
        return {
            "worker_id": worker_id,
            "total_violations": state.total_violations,
            "total_alerts_fired": state.total_alerts_fired,
            "alert_active": state.alert_active,
            "zone_duration_s": (
                round(time.monotonic() - state.zone_entry_time, 1)
                if state.zone_entry_time else 0.0
            ),
            "window_hits": sum(state.frame_window),
            "window_size": len(state.frame_window),
        }

    def all_worker_ids(self) -> list[int]:
        return list(self._workers.keys())

    # ── Internal ───────────────────────────────────────────────────────────────

    def _get_or_create(self, worker_id: int) -> _WorkerState:
        if worker_id not in self._workers:
            self._workers[worker_id] = _WorkerState()
        return self._workers[worker_id]
