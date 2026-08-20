"""Tests for violation purging, worker deletion, and date range filtering."""

import pytest
import asyncio
from datetime import datetime, timedelta
from src.core import db


@pytest.mark.asyncio
async def test_date_range_filtering_and_purging():
    # Record a test violation
    evt_id = await db.record_violation(
        worker_id="TestWorker-999",
        zone_id="General Plant Floor",
        violation_type="Missing helmet",
        detected_ppe=["vest"],
        missing_ppe=["helmet"],
        confidence=0.95
    )

    assert evt_id is not None

    # Test filtering by hours / last_24h
    res_24h = await db.get_filtered_violations(date_range="hours", worker_id="TestWorker-999")
    assert len(res_24h) > 0
    assert res_24h[0]["workerId"] == "TestWorker-999"
    # Check timestamp ends with 'Z' for UTC/IST conversion
    assert res_24h[0]["timestamp"].endswith("Z")

    # Test purging specific violation ID
    ok = await db.delete_violations_bulk([evt_id])
    assert ok is True

    res_after = await db.get_filtered_violations(worker_id="TestWorker-999")
    assert not any(v["id"] == evt_id for v in res_after)


@pytest.mark.asyncio
async def test_worker_deletion():
    w_id = "TestWorker-888"
    evt1 = await db.record_violation(
        worker_id=w_id,
        zone_id="General Plant Floor",
        violation_type="Missing helmet",
        detected_ppe=["vest"],
        missing_ppe=["helmet"],
        confidence=0.92
    )
    evt2 = await db.record_violation(
        worker_id=w_id,
        zone_id="General Plant Floor",
        violation_type="Missing vest",
        detected_ppe=["helmet"],
        missing_ppe=["vest"],
        confidence=0.88
    )

    # Verify worker appears in worker list
    workers = await db.get_workers()
    assert any(w["id"] == w_id for w in workers)

    # Delete worker
    del_ok = await db.delete_worker(w_id)
    assert del_ok is True

    # Verify worker records are purged
    res = await db.get_filtered_violations(worker_id=w_id)
    assert len(res) == 0
