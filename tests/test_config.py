"""Tests for configuration defaults and environment variable overrides."""

import os
import importlib
import pytest


def test_default_detection_conf():
    from src.core import config
    assert 0.0 < config.DETECTION_CONF < 1.0


def test_temporal_window_positive():
    from src.core import config
    assert config.TEMPORAL_WINDOW > 0


def test_temporal_min_hits_leq_window():
    from src.core import config
    assert config.TEMPORAL_MIN_HITS <= config.TEMPORAL_WINDOW


def test_zone_rules_not_empty():
    from src.core import config
    assert len(config.ZONE_RULES) > 0
    for zone, ppe in config.ZONE_RULES.items():
        assert isinstance(ppe, set)
        assert len(ppe) > 0, f"Zone '{zone}' has no required PPE"


def test_ppe_classes_list():
    from src.core import config
    assert "helmet" in config.PPE_CLASSES
    assert "vest"   in config.PPE_CLASSES
    assert "boots"  in config.PPE_CLASSES


def test_env_override_mqtt_broker(monkeypatch):
    monkeypatch.setenv("MQTT_BROKER", "my.private.broker")
    import importlib
    from src.core import config as cfg_module
    importlib.reload(cfg_module)
    assert cfg_module.MQTT_BROKER == "my.private.broker"
    # Restore
    monkeypatch.delenv("MQTT_BROKER", raising=False)
    importlib.reload(cfg_module)
