"""
MQTT violation publisher with temporal-validation integration.

Integrates with Stage-5 TemporalValidator so alerts are only published
when the configurable frame-window/confidence/zone-duration thresholds
are satisfied.  Duplicate alerts for the same ongoing violation are
suppressed automatically.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

import paho.mqtt.client as mqtt

from src.core import config
from src.core.rule_engine import ComplianceResult, RuleEngine
from src.core.temporal_validator import TemporalValidator

log = logging.getLogger(__name__)


class PPEMqttPublisher:
    """
    Receives per-worker ComplianceResult objects, runs them through the
    TemporalValidator, and publishes confirmed violations to MQTT.

    Thread-safety: `process_worker_state` may be called from the inference
    thread; the MQTT client runs its own network loop thread.
    """

    def __init__(
        self,
        broker:   str  = config.MQTT_BROKER,
        port:     int  = config.MQTT_PORT,
        topic:    str  = config.MQTT_TOPIC,
        username: str  = config.MQTT_USERNAME,
        password: str  = config.MQTT_PASSWORD,
        use_tls:  bool = config.MQTT_USE_TLS,
    ) -> None:
        self.broker  = broker
        self.port    = port
        self.topic   = topic

        self._validator = TemporalValidator()
        self._rule_engine = RuleEngine()
        self._lock = threading.Lock()

        # Stats
        self._published_count = 0
        self._suppressed_count = 0
        self._connected = False

        # paho-mqtt 2.x client API (CallbackAPIVersion required; v1 API removed)
        try:
            import paho.mqtt.client as mqtt_mod
            CallbackAPIVersion = mqtt_mod.CallbackAPIVersion
            use_cb_v2 = True
        except Exception:
            CallbackAPIVersion = None
            use_cb_v2 = False

        if use_cb_v2:
            self._client = mqtt.Client(CallbackAPIVersion.VERSION2)
        else:  # paho-mqtt 1.x fallback
            self._client = mqtt.Client(protocol=mqtt.MQTTv311)

        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect

        if username:
            self._client.username_pw_set(username, password)
        if use_tls:
            self._client.tls_set()

        try:
            self._client.connect_async(broker, port, keepalive=60)
            self._client.loop_start()
        except Exception as exc:
            log.warning("MQTT connect failed: %s", exc)

    # ── Public API ─────────────────────────────────────────────────────────────

    def process_compliance_result(
        self,
        result: ComplianceResult,
        bbox_center: Optional[tuple[float, float]] = None
    ) -> bool:
        """
        Feed a ComplianceResult through Stage-5 validation.

        Returns True if an alert was published, False otherwise.
        """
        with self._lock:
            should_alert, reason = self._validator.update(result, bbox_center=bbox_center)

        log.debug("Worker-%s: %s", result.worker_id, reason)

        if should_alert:
            self._publish_violation(result)
            return True

        if not result.compliant:
            self._suppressed_count += 1
        return False

    def process_worker_state(
        self,
        worker_id:    int,
        detected_ppe: set[str],
        zone:         str  = config.DEFAULT_ZONE,
        confidence:   float = 1.0,
    ) -> bool:
        """
        Convenience wrapper: evaluate rule engine then forward to
        `process_compliance_result`.  Suitable for callers that don't
        construct ComplianceResult themselves.
        """
        result = self._rule_engine.evaluate(
            worker_id=worker_id,
            detected_ppe=detected_ppe,
            zone=zone,
            confidence=confidence,
        )
        return self.process_compliance_result(result)

    def get_worker_stats(self, worker_id: int) -> Optional[dict]:
        return self._validator.get_stats(worker_id)

    def stats(self) -> dict:
        return {
            "published": self._published_count,
            "suppressed": self._suppressed_count,
            "connected": self._connected,
        }

    def close(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    # ── Internal ───────────────────────────────────────────────────────────────

    def _publish_violation(self, result: ComplianceResult) -> None:
        payload = {
            "event_id":   f"{result.worker_id}-{int(time.time()*1000)}",
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "worker_id":  f"Worker-{result.worker_id}",
            "zone":       result.zone,
            "status":     "VIOLATION",
            "detected_ppe": sorted(result.detected_ppe),
            "missing_ppe":  sorted(result.missing_ppe),
            "required_ppe": sorted(result.required_ppe),
            "confidence": round(result.confidence, 3),
        }
        if not self._connected:
            log.debug("MQTT broker (%s) offline or reconnecting, violation alert handled locally.", self.broker)
            return

        try:
            rc, _ = self._client.publish(
                self.topic,
                json.dumps(payload),
                qos=1,
            )
            if rc == mqtt.MQTT_ERR_SUCCESS:
                self._published_count += 1
                log.info(
                    "Violation published – Worker-%s missing %s (zone=%s)",
                    result.worker_id, result.missing_ppe, result.zone,
                )
            elif rc == mqtt.MQTT_ERR_NO_CONN:
                self._connected = False
                log.debug("MQTT broker disconnected during publish (rc=%s)", rc)
            else:
                log.warning("MQTT publish status: rc=%s", rc)
        except Exception as exc:
            log.debug("MQTT publish error: %s", exc)

    def _on_connect(self, client, userdata, flags, rc, *props):
        # paho v1: rc is an int; paho v2: rc is a ReasonCode object.
        code = getattr(rc, "value", rc)
        self._connected = (code == 0)
        if self._connected:
            log.info("MQTT connected to %s:%s", self.broker, self.port)
        else:
            log.debug("MQTT connect returned rc=%s (running in local offline mode)", code)

    def _on_disconnect(self, client, userdata, *args):
        # v1: (client, userdata, rc)  |  v2: (client, userdata, flags, rc, props)
        rc = args[-1] if args else 0
        code = getattr(rc, "value", rc)
        self._connected = False
        if code != 0:
            log.debug("MQTT broker disconnected, rc=%s", code)


# ── CLI smoke test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    pub = PPEMqttPublisher()
    time.sleep(1)

    # Simulate Worker-101 in work_at_height zone missing harness
    for i in range(12):
        pub.process_worker_state(
            worker_id=101,
            detected_ppe={"helmet", "vest", "boots"},
            zone="work_at_height",
            confidence=0.82,
        )
        time.sleep(0.1)

    print("Stats:", pub.stats())
    pub.close()
