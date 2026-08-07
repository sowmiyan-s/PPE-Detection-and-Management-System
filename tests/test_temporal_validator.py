"""Tests for Stage-5 temporal validation."""

import time
import pytest
from unittest.mock import patch

from src.core.rule_engine import ComplianceResult
from src.core.temporal_validator import TemporalValidator
from src.core import config


def _make_result(compliant: bool, worker_id: int = 1,
                 confidence: float = 0.9,
                 missing: set = None) -> ComplianceResult:
    missing = missing or (set() if compliant else {"helmet"})
    return ComplianceResult(
        worker_id=worker_id,
        zone="general_plant",
        required_ppe={"helmet", "vest"},
        detected_ppe={"vest"} if not compliant else {"helmet", "vest"},
        missing_ppe=missing,
        extra_ppe=set(),
        compliant=compliant,
        confidence=confidence,
    )


# ── Basic behaviour ───────────────────────────────────────────────────────────

def test_no_alert_during_warmup():
    """Alert should NOT fire until the window is full."""
    tv = TemporalValidator()
    for _ in range(config.TEMPORAL_WINDOW - 1):
        alert, reason = tv.update(_make_result(compliant=False))
        assert alert is False, f"Early alert fired: {reason}"


def test_alert_fires_after_full_window():
    """Alert SHOULD fire once the window is full with enough hits."""
    tv = TemporalValidator()
    # Fill zone duration requirement by mocking time
    with patch("src.core.temporal_validator.time.monotonic", side_effect=[
        0.0,                                   # first zone_entry_time
        *[config.TEMPORAL_MIN_ZONE_SECS + 1.0] * (config.TEMPORAL_WINDOW * 2)
    ]):
        fired = False
        for _ in range(config.TEMPORAL_WINDOW):
            alert, _ = tv.update(_make_result(compliant=False))
            if alert:
                fired = True
                break
        assert fired, "Alert never fired after full window"


def test_compliant_frame_does_not_alert():
    tv = TemporalValidator()
    for _ in range(config.TEMPORAL_WINDOW + 5):
        alert, _ = tv.update(_make_result(compliant=True))
        assert alert is False


def test_low_confidence_suppresses_alert():
    """Alert should be suppressed when confidence is below threshold."""
    tv = TemporalValidator()
    with patch("src.core.temporal_validator.time.monotonic",
               return_value=config.TEMPORAL_MIN_ZONE_SECS + 1.0):
        for _ in range(config.TEMPORAL_WINDOW):
            alert, reason = tv.update(_make_result(
                compliant=False,
                confidence=config.TEMPORAL_MIN_CONF - 0.1,
            ))
        assert alert is False
        assert "confidence" in reason


def test_same_ongoing_violation_not_repeated():
    """After an alert fires, the same continuing violation should not re-fire."""
    tv = TemporalValidator()
    with patch("src.core.temporal_validator.time.monotonic",
               return_value=config.TEMPORAL_MIN_ZONE_SECS + 1.0):
        alert_count = 0
        for _ in range(config.TEMPORAL_WINDOW * 3):
            alert, _ = tv.update(_make_result(compliant=False))
            if alert:
                alert_count += 1
        # Should fire at most once for the same ongoing violation
        assert alert_count <= 1


def test_alert_resumes_after_compliance():
    """Alert should fire again if a new violation starts after a compliant period."""
    tv = TemporalValidator()
    with patch("src.core.temporal_validator.time.monotonic",
               side_effect=[0.0] + [config.TEMPORAL_MIN_ZONE_SECS + 5.0] * 50):
        # First violation cycle
        for _ in range(config.TEMPORAL_WINDOW):
            tv.update(_make_result(compliant=False))

        # Compliant period clears state
        for _ in range(5):
            tv.update(_make_result(compliant=True))

        # Second violation cycle
        fired = False
        for _ in range(config.TEMPORAL_WINDOW):
            alert, _ = tv.update(_make_result(compliant=False))
            if alert:
                fired = True
        assert fired, "Alert did not fire after compliance cleared state"


# ── Stats ─────────────────────────────────────────────────────────────────────

def test_get_stats_unknown_worker_returns_none():
    tv = TemporalValidator()
    assert tv.get_stats(999) is None


def test_get_stats_returns_dict():
    tv = TemporalValidator()
    tv.update(_make_result(compliant=False, worker_id=42))
    stats = tv.get_stats(42)
    assert stats is not None
    assert stats["worker_id"] == 42
    assert "total_violations" in stats
    assert "window_hits" in stats


def test_reset_worker():
    tv = TemporalValidator()
    tv.update(_make_result(compliant=False, worker_id=7))
    tv.reset_worker(7)
    assert tv.get_stats(7) is None


def test_multiple_workers_independent():
    tv = TemporalValidator()
    tv.update(_make_result(compliant=False, worker_id=1))
    tv.update(_make_result(compliant=True,  worker_id=2))
    s1 = tv.get_stats(1)
    s2 = tv.get_stats(2)
    assert s1["total_violations"] == 1
    assert s2["total_violations"] == 0
