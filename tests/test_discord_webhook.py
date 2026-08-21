"""
Unit test suite for Discord Webhook Notification Dispatcher.
Verifies payload formatting, configuration persistence in SQLite,
on/off toggle controls, and dispatch behavior.
"""

import pytest
from unittest.mock import patch, MagicMock
from src.core import discord_webhook
from src.core import sqlite_db


def test_webhook_config_persistence():
    """Verify Discord webhook settings save and load accurately in SQL database."""
    test_cfg = {
        "enabled": True,
        "url": "https://discord.com/api/webhooks/1234567890/testtoken",
        "min_confidence": 0.65,
    }
    
    saved = discord_webhook.save_webhook_config(test_cfg)
    assert saved["enabled"] is True
    assert saved["url"] == "https://discord.com/api/webhooks/1234567890/testtoken"
    assert abs(saved["min_confidence"] - 0.65) < 1e-4

    loaded = discord_webhook.get_webhook_config()
    assert loaded["enabled"] is True
    assert loaded["url"] == "https://discord.com/api/webhooks/1234567890/testtoken"

    # Disable webhook toggle
    disabled_cfg = discord_webhook.save_webhook_config({"enabled": False, "url": test_cfg["url"]})
    assert disabled_cfg["enabled"] is False
    assert discord_webhook.is_webhook_enabled() is False


def test_format_discord_embed():
    """Verify rich embed payload generation for Discord webhook."""
    embed_data = discord_webhook.format_discord_embed(
        worker_id="Worker-202",
        zone_id="High Voltage Bay",
        camera_id="CAM-02",
        missing_ppe=["Helmet", "Vest"],
        detected_ppe=["Boots"],
        confidence=0.88,
        is_test=False,
    )

    assert embed_data["username"] == "Cerberus AI Safety Bot"
    assert len(embed_data["embeds"]) == 1
    embed = embed_data["embeds"][0]
    assert "Worker-202" in embed["description"]
    assert embed["color"] == 0xFF0033
    fields = {f["name"]: f["value"] for f in embed["fields"]}
    assert fields["👤 Worker ID"] == "`Worker-202`"
    assert fields["🚨 Missing PPE"] == "**Helmet, Vest**"


@patch("urllib.request.urlopen")
def test_dispatch_webhook_payload_success(mock_urlopen):
    """Verify successful dispatch to Discord webhook endpoint."""
    mock_resp = MagicMock()
    mock_resp.status = 204
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    payload = {"username": "Cerberus AI", "content": "Test"}
    ok, msg = discord_webhook.dispatch_webhook_payload(payload, "https://discord.com/api/webhooks/dummy")
    assert ok is True
    assert "successfully" in msg.lower()


@patch("urllib.request.urlopen")
def test_send_test_discord_notification(mock_urlopen):
    """Verify test Discord alert sender."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_urlopen.return_value.__enter__.return_value = mock_resp

    ok, msg = discord_webhook.send_test_discord_notification("https://discord.com/api/webhooks/test")
    assert ok is True
