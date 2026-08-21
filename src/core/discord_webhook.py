"""
Discord Webhook Notification Dispatcher.

Provides real-time Discord embed alerts for safety violations with on/off toggle,
URL configuration, minimum confidence gating, and test notification dispatching.
"""

from __future__ import annotations

import json
import logging
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Optional

from src.core import sqlite_db

log = logging.getLogger(__name__)

# Default in-memory state
_WEBHOOK_CONFIG_CACHE: dict[str, Any] = sqlite_db.get_webhook_config_sql()


def get_webhook_config() -> dict[str, Any]:
    """Retrieve current Discord webhook configuration."""
    global _WEBHOOK_CONFIG_CACHE
    db_config = sqlite_db.get_webhook_config_sql()
    _WEBHOOK_CONFIG_CACHE = db_config
    return _WEBHOOK_CONFIG_CACHE


def save_webhook_config(data: dict[str, Any]) -> dict[str, Any]:
    """Update and persist Discord webhook configuration."""
    global _WEBHOOK_CONFIG_CACHE
    enabled = bool(data.get("enabled", False))
    url = str(data.get("url") or "").strip()
    min_confidence = float(data.get("min_confidence", 0.50))

    new_config = {
        "enabled": enabled,
        "url": url,
        "min_confidence": min_confidence,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    
    ok = sqlite_db.save_webhook_config_sql(new_config)
    if ok:
        _WEBHOOK_CONFIG_CACHE = new_config
    return _WEBHOOK_CONFIG_CACHE


def is_webhook_enabled() -> bool:
    """Check if Discord webhook alerts are enabled with a valid URL."""
    cfg = get_webhook_config()
    return bool(cfg.get("enabled")) and bool(cfg.get("url", "").startswith("http"))


def format_discord_embed(
    worker_id: str,
    zone_id: str,
    camera_id: str,
    missing_ppe: list[str],
    detected_ppe: list[str] | None = None,
    confidence: float = 0.0,
    timestamp: str | None = None,
    is_test: bool = False,
) -> dict[str, Any]:
    """Build a rich Discord embed card for violation alerts."""
    now_str = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    missing_str = ", ".join(missing_ppe) if missing_ppe else "General Safety Hazard"
    detected_str = ", ".join(detected_ppe) if detected_ppe else "None"
    conf_pct = f"{int(round(confidence * 100))}%" if confidence > 0 else "—"

    if is_test:
        title = "🧪 Discord Webhook Connection Test — Cerberus AI"
        description = "This is a test notification from Cerberus AI Industrial PPE Compliance Engine. Discord alerts are working properly!"
        color = 0x00FF88  # Emerald green
    else:
        title = f"🚨 PPE Safety Violation Alert — {zone_id}"
        description = f"Worker **{worker_id}** violated PPE safety rules in **{zone_id}**."
        color = 0xFF0033  # Red alert

    fields = [
        {"name": "👤 Worker ID", "value": f"`{worker_id}`", "inline": True},
        {"name": "📍 Zone", "value": f"`{zone_id}`", "inline": True},
        {"name": "📹 Camera ID", "value": f"`{camera_id}`", "inline": True},
        {"name": "🚨 Missing PPE", "value": f"**{missing_str}**", "inline": False},
        {"name": "✅ Compliant PPE", "value": f"`{detected_str}`", "inline": True},
        {"name": "📊 Confidence", "value": f"`{conf_pct}`", "inline": True},
        {"name": "⏰ Timestamp", "value": f"`{now_str}`", "inline": False},
    ]

    return {
        "username": "Cerberus AI Safety Bot",
        "avatar_url": "https://raw.githubusercontent.com/Vidhyasree14/Cerberus-AI/main/public/favicon.ico",
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "fields": fields,
                "footer": {
                    "text": "Cerberus AI — Industrial PPE Compliance & Safety Intelligence Platform"
                },
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        ],
    }


def dispatch_webhook_payload(payload: dict[str, Any], webhook_url: str) -> tuple[bool, str]:
    """Execute synchronous HTTP POST to Discord webhook URL."""
    if not webhook_url or not webhook_url.startswith("http"):
        return False, "Invalid or missing Webhook URL"

    try:
        json_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=json_bytes,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Cerberus-AI-SafetyBot/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            if resp.status in (200, 204):
                return True, "Alert sent successfully to Discord"
            return False, f"Discord returned HTTP status code {resp.status}"
    except urllib.error.HTTPError as http_err:
        log.error("Discord Webhook HTTP Error: %s", http_err)
        return False, f"Discord HTTP Error: {http_err.code} {http_err.reason}"
    except Exception as exc:
        log.error("Discord Webhook dispatch failed: %s", exc)
        return False, f"Network error: {str(exc)}"


def send_discord_alert_async(violation_data: dict[str, Any]) -> None:
    """Non-blocking background thread worker to dispatch Discord webhook alert."""
    cfg = get_webhook_config()
    if not cfg.get("enabled"):
        return

    url = cfg.get("url", "").strip()
    if not url.startswith("http"):
        return

    min_conf = float(cfg.get("min_confidence", 0.50))
    event_conf = float(violation_data.get("confidence", 1.0))
    if event_conf < min_conf:
        log.debug("Skipping Discord webhook: event confidence %.2f < threshold %.2f", event_conf, min_conf)
        return

    payload = format_discord_embed(
        worker_id=violation_data.get("worker_id") or violation_data.get("workerId") or "Worker-101",
        zone_id=violation_data.get("zone_id") or violation_data.get("zoneId") or "General Plant Floor",
        camera_id=violation_data.get("camera_id") or violation_data.get("cameraId") or "CAM-01",
        missing_ppe=violation_data.get("missing_ppe") or violation_data.get("missing") or [],
        detected_ppe=violation_data.get("detected_ppe") or violation_data.get("detected") or [],
        confidence=event_conf,
        timestamp=violation_data.get("timestamp"),
        is_test=False,
    )

    thread = threading.Thread(
        target=dispatch_webhook_payload,
        args=(payload, url),
        daemon=True,
        name="DiscordWebhookDispatcher",
    )
    thread.start()


def send_test_discord_notification(custom_url: Optional[str] = None) -> tuple[bool, str]:
    """Send an immediate test alert to verify Discord webhook integration."""
    cfg = get_webhook_config()
    url = (custom_url or cfg.get("url", "")).strip()
    if not url or not url.startswith("http"):
        return False, "Invalid Discord Webhook URL. Please enter a URL starting with https://discord.com/api/webhooks/..."

    payload = format_discord_embed(
        worker_id="Worker-TEST",
        zone_id="Test Inspection Zone",
        camera_id="CAM-TEST",
        missing_ppe=["Helmet", "Vest"],
        detected_ppe=["Boots"],
        confidence=0.95,
        is_test=True,
    )

    return dispatch_webhook_payload(payload, url)
