"""Tests for Stage 5 Spatial-Temporal Event Debouncing."""

import time
import pytest
from unittest.mock import patch
from src.core.rule_engine import ComplianceResult
from src.core.temporal_validator import TemporalValidator
from src.core import config


def _make_violation_result(worker_id: int, zone: str = "General Plant Floor", missing: set = None) -> ComplianceResult:
    return ComplianceResult(
        worker_id=worker_id,
        zone=zone,
        required_ppe={"helmet", "vest"},
        detected_ppe={"vest"},
        missing_ppe=missing or {"helmet"},
        extra_ppe=set(),
        compliant=False,
        confidence=0.90,
    )


def test_spatial_debouncer_suppresses_nearby_duplicate_worker_alert():
    tv = TemporalValidator()
    res1 = _make_violation_result(worker_id=101)
    res2 = _make_violation_result(worker_id=202)  # Different worker ID in same location

    curr_time = 100.0

    def mock_time():
        return curr_time

    with patch("src.core.temporal_validator.time.monotonic", side_effect=mock_time):
        # Warm up worker 101 to fire first alert at location (100, 100)
        alert1 = False
        for i in range(config.TEMPORAL_WINDOW + 2):
            curr_time = 100.0 + (i * 0.6)  # Advance time by 0.6s per frame (> 5s dwell)
            a, r = tv.update(res1, bbox_center=(100.0, 100.0))
            if a:
                alert1 = True

        assert alert1 is True, "First worker alert must fire!"

        # Warm up worker 202 at nearby location (120, 110) - within 180px spatial radius
        alert2 = False
        reasons = []
        for i in range(config.TEMPORAL_WINDOW + 2):
            curr_time = 108.0 + (i * 0.6)  # 8 seconds later (within 12s cooldown)
            a, r = tv.update(res2, bbox_center=(120.0, 110.0))
            if r:
                reasons.append(r)
            if a:
                alert2 = True

        assert alert2 is False, "Nearby violation at same location must be debounced!"
        assert any("debounced spatial event" in r for r in reasons)
