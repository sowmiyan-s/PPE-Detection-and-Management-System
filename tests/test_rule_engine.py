"""Tests for Stage-4 zone rule engine."""

import pytest
from src.core.rule_engine import RuleEngine, ZoneConfig, ComplianceResult


# ── ZoneConfig ────────────────────────────────────────────────────────────────

def test_zone_config_compliant():
    zone = ZoneConfig(name="general_plant", required_ppe={"helmet", "vest"})
    result = zone.check_compliance(worker_id=1, detected_ppe={"helmet", "vest"})
    assert result.compliant is True
    assert result.missing_ppe == set()


def test_zone_config_violation():
    zone = ZoneConfig(name="construction", required_ppe={"helmet", "vest", "boots"})
    result = zone.check_compliance(worker_id=2, detected_ppe={"helmet", "vest"})
    assert result.compliant is False
    assert result.missing_ppe == {"boots"}


def test_zone_config_extra_ppe_allowed():
    zone = ZoneConfig(name="general_plant", required_ppe={"helmet", "vest"})
    result = zone.check_compliance(worker_id=3, detected_ppe={"helmet", "vest", "boots"})
    assert result.compliant is True
    assert "boots" in result.extra_ppe


def test_zone_config_empty_detected():
    zone = ZoneConfig(name="hazardous_material",
                      required_ppe={"helmet", "safety-suit", "boots", "gloves", "goggles"})
    result = zone.check_compliance(worker_id=4, detected_ppe=set())
    assert result.compliant is False
    assert result.missing_ppe == zone.required_ppe


# ── RuleEngine ────────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    return RuleEngine()


def test_engine_evaluates_known_zone(engine):
    result = engine.evaluate(worker_id=1,
                             detected_ppe={"helmet", "vest"},
                             zone="general_plant")
    assert result.compliant is True
    assert result.zone == "general_plant"


def test_engine_hazardous_material_requires_full_kit(engine):
    result = engine.evaluate(worker_id=2,
                             detected_ppe={"helmet", "safety-suit"},
                             zone="hazardous_material")
    assert result.compliant is False
    assert "boots" in result.missing_ppe
    assert "gloves" in result.missing_ppe
    assert "goggles" in result.missing_ppe


def test_engine_unknown_zone_falls_back(engine):
    result = engine.evaluate(worker_id=3,
                             detected_ppe={"helmet", "vest"},
                             zone="nonexistent_zone")
    # Should not raise, should return some compliance result
    assert isinstance(result, ComplianceResult)


def test_engine_add_zone(engine):
    engine.add_zone("warehouse", {"helmet"}, description="Warehouse area")
    result = engine.evaluate(worker_id=5, detected_ppe={"helmet"}, zone="warehouse")
    assert result.compliant is True


def test_engine_remove_zone(engine):
    engine.add_zone("temp", {"helmet"})
    removed = engine.remove_zone("temp")
    assert removed is True
    assert engine.get_zone("temp") is None


def test_engine_remove_nonexistent_zone(engine):
    removed = engine.remove_zone("does_not_exist")
    assert removed is False


def test_engine_list_zones(engine):
    zones = engine.list_zones()
    assert isinstance(zones, list)
    assert all("name" in z and "required_ppe" in z for z in zones)


def test_engine_confidence_stored(engine):
    result = engine.evaluate(worker_id=6, detected_ppe={"helmet", "vest"},
                             zone="general_plant", confidence=0.88)
    assert result.confidence == pytest.approx(0.88)
