"""
Test suite for Zone Configuration persistence and database operations.
Verifies CRUD operations on zones in SQLite SQL database, temporal parameters,
and rule engine synchronization.
"""

import pytest
import json
from src.core import sqlite_db
from src.core import db
from src.core.rule_engine import RuleEngine
from src.core.detector import PPEDetector


def test_sqlite_zone_crud():
    """Verify SQLite SQL database directly saves, retrieves, and deletes zones."""
    test_zone = {
        "id": "Test Inspection Bay",
        "name": "Test Inspection Bay",
        "description": "High voltage test area",
        "required_ppe": ["helmet", "vest", "boots", "glasses"],
        "frame_threshold": 9,
        "dwell_seconds": 4,
        "confidence": 0.75
    }
    
    # Save to SQLite
    ok = sqlite_db.save_zone_sql(test_zone)
    assert ok is True
    
    # Retrieve from SQLite
    zones = sqlite_db.get_zones_sql()
    found = next((z for z in zones if z["id"] == "Test Inspection Bay"), None)
    assert found is not None
    assert found["name"] == "Test Inspection Bay"
    assert found["description"] == "High voltage test area"
    assert "helmet" in found["required_ppe"]
    assert "glasses" in found["required_ppe"]
    assert found["frame_threshold"] == 9
    assert found["dwell_seconds"] == 4
    assert abs(found["confidence"] - 0.75) < 1e-4

    # Update in SQLite
    test_zone["frame_threshold"] = 7
    test_zone["dwell_seconds"] = 3
    test_zone["confidence"] = 0.85
    test_zone["required_ppe"] = ["helmet", "vest"]
    ok = sqlite_db.save_zone_sql(test_zone)
    assert ok is True
    
    zones_updated = sqlite_db.get_zones_sql()
    found_updated = next((z for z in zones_updated if z["id"] == "Test Inspection Bay"), None)
    assert found_updated is not None
    assert found_updated["frame_threshold"] == 7
    assert found_updated["dwell_seconds"] == 3
    assert abs(found_updated["confidence"] - 0.85) < 1e-4
    assert set(found_updated["required_ppe"]) == {"helmet", "vest"}

    # Delete from SQLite
    del_ok = sqlite_db.delete_zone_sql("Test Inspection Bay")
    assert del_ok is True
    
    zones_after = sqlite_db.get_zones_sql()
    assert not any(z["id"] == "Test Inspection Bay" for z in zones_after)


@pytest.mark.asyncio
async def test_db_layer_zone_sync():
    """Verify src.core.db layer keeps database, memory, and cache in sync."""
    zone_data = {
        "id": "Async Test Zone",
        "name": "Async Test Zone",
        "kind": "Specialized Lab",
        "required_ppe": ["helmet", "vest", "boots"],
        "frameThreshold": 6,
        "dwellSeconds": 5,
        "confidence": 0.80
    }
    
    save_ok = await db.save_zone(zone_data)
    assert save_ok is True
    
    zones = await db.get_zones()
    found = next((z for z in zones if z.get("id") == "Async Test Zone"), None)
    assert found is not None
    assert found.get("frame_threshold") == 6 or found.get("frameThreshold") == 6
    assert found.get("dwell_seconds") == 5 or found.get("dwellSeconds") == 5
    assert set(found.get("required_ppe", [])) == {"helmet", "vest", "boots"}

    # Clean up
    del_ok = await db.delete_zone("Async Test Zone")
    assert del_ok is True
    
    zones_after = await db.get_zones()
    assert not any(z.get("id") == "Async Test Zone" for z in zones_after)


def test_rule_engine_and_temporal_thresholds():
    """Verify RuleEngine and PPEDetector update with temporal parameters."""
    detector = PPEDetector()
    
    detector.update_zone_config(
        zone_name="Dynamic Zone",
        required_ppe={"helmet", "boots"},
        frame_threshold=5,
        dwell_seconds=3,
        confidence=0.70
    )
    
    # Evaluate rule engine
    res = detector._rule_engine.evaluate(
        worker_id=999,
        detected_ppe={"helmet"},
        zone="Dynamic Zone",
        confidence=0.70
    )
    assert res.compliant is False
    assert "boots" in res.missing_ppe

    # Check temporal validator zone thresholds
    zone_th = detector._temporal_validator._zone_thresholds.get("Dynamic Zone", {})
    assert zone_th.get("min_hits") == 5
    assert zone_th.get("min_zone_secs") == 3.0
    assert abs(zone_th.get("min_conf") - 0.70) < 1e-4
