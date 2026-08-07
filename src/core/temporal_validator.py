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
    Maintains per-worker sliding-window state and decides when to fire an alert.

    Usage
    -----
    validator = TemporalValidator()
    should_alert, reason = validator.update(result)
    if should_alert:
        publish_violation(result)
    """

    def __init__(self) -> None:
        self._workers: dict[int, _WorkerState] = {}

    # ── Public API ─────────────────────────────────────────────────────────────

    def update(self, result: ComplianceResult) -> tuple[bool, str]:
        """
        Feed one compliance result for one worker.

        Returns
        -------
        (should_alert, reason)
            should_alert – True if all temporal conditions are met and this is a
                           new (or resumed) violation event.
            reason       – Human-readable explanation.
        """
        state = self._get_or_create(result.worker_id)
        now   = time.monotonic()

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

        if hits < config.TEMPORAL_MIN_HITS:
            return False, (
                f"insufficient hits: {hits}/{config.TEMPORAL_WINDOW} "
                f"(need {config.TEMPORAL_MIN_HITS})"
            )

        if result.confidence < config.TEMPORAL_MIN_CONF:
            return False, (
                f"confidence too low: {result.confidence:.2f} "
                f"< {config.TEMPORAL_MIN_CONF}"
            )

        if zone_duration < config.TEMPORAL_MIN_ZONE_SECS:
            return False, (
                f"zone duration too short: {zone_duration:.1f}s "
                f"< {config.TEMPORAL_MIN_ZONE_SECS}s"
            )

        # All conditions met – suppress if this is the same ongoing violation
        if state.alert_active and result.missing_ppe == state.last_missing_ppe:
            return False, "suppressed – same ongoing violation"

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
