# EdgeVision PPE Platform – API Documentation

## FastAPI WebSocket Server (`server.py`)

Base URL: `http://<host>:8000`

---

### `GET /`

Returns the live monitoring HTML dashboard.

**Response:** `text/html`

---

### `GET /health`

Returns system health status.

**Response:** `application/json`

```json
{
  "status": "ok",
  "fps": 18.4,
  "zone": "work_at_height",
  "ws_connections": 2
}
```

---

### `GET /zones`

Returns all configured safety zones and the currently active zone.

**Response:**
```json
{
  "zones": [
    {
      "name": "general_plant",
      "required_ppe": ["helmet", "vest"],
      "description": ""
    },
    {
      "name": "work_at_height",
      "required_ppe": ["boots", "helmet", "hook", "safety_belt", "vest"],
      "description": ""
    }
  ],
  "active": "general_plant"
}
```

---

### `POST /zones`

Switch the active safety zone.

**Request body:**
```json
{ "zone": "work_at_height" }
```

**Response:**
```json
{ "active": "work_at_height" }
```

---

### `WebSocket /ws`

Streams real-time inference results as JSON messages.

**Connection:** `ws://<host>:8000/ws`

**Message format (server → client):**
```json
{
  "frame":   "<base64-encoded JPEG>",
  "workers": [
    {
      "worker_id":   "Worker-101",
      "zone":        "work_at_height",
      "detected_ppe": ["helmet", "vest", "boots"],
      "missing_ppe":  ["safety_belt", "hook"],
      "compliant":    false,
      "confidence":   0.82
    }
  ],
  "fps":  18.4,
  "zone": "work_at_height"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `frame` | string | Base64-encoded JPEG frame with annotation overlays |
| `workers` | array | One entry per tracked worker in the current frame |
| `fps` | float | Current inference throughput |
| `zone` | string | Active safety zone name |

**Worker object fields:**

| Field | Type | Description |
|-------|------|-------------|
| `worker_id` | string | `"Worker-<tracking_id>"` |
| `zone` | string | Active zone for this frame |
| `detected_ppe` | string[] | PPE classes detected on this worker |
| `missing_ppe` | string[] | Required PPE that is absent |
| `compliant` | boolean | True if all required PPE is present |
| `confidence` | float | Mean detection confidence (0–1) |

---

## MQTT Alert Schema

Topic: `factory/ppe_violations` (configurable via `MQTT_TOPIC` env var)

**Message payload:**
```json
{
  "event_id":    "101-1722950400000",
  "timestamp":   "2026-07-25T12:00:00.000Z",
  "worker_id":   "Worker-101",
  "zone":        "work_at_height",
  "status":      "VIOLATION",
  "detected_ppe": ["helmet", "vest", "boots"],
  "missing_ppe":  ["safety_belt", "hook"],
  "required_ppe": ["boots", "helmet", "hook", "safety_belt", "vest"],
  "confidence":  0.823
}
```

Alerts are only published after Stage-5 temporal validation passes (default: 8 of
the last 10 frames show the violation, confidence ≥ 0.30, worker in zone ≥ 2 s).

---

## Python Module APIs

### `config.py`

All tunable parameters. Override via environment variables:

| Env var | Default | Description |
|---------|---------|-------------|
| `MQTT_BROKER` | `test.mosquitto.org` | MQTT broker hostname |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_TOPIC` | `factory/ppe_violations` | Publish topic |
| `MQTT_USERNAME` | `` | Username (leave empty for no auth) |
| `MQTT_PASSWORD` | `` | Password |
| `MQTT_USE_TLS` | `false` | Enable TLS |
| `MODEL_PATH` | `ppe_training/custom_model/weights/best.pt` | YOLO weights |
| `DETECTION_CONF` | `0.20` | Minimum detection confidence |
| `TEMPORAL_WINDOW` | `10` | Frame window for temporal validation |
| `TEMPORAL_MIN_HITS` | `8` | Minimum violation frames in window |
| `TEMPORAL_MIN_CONF` | `0.30` | Minimum confidence for alert |
| `TEMPORAL_MIN_ZONE_SECS` | `2.0` | Minimum zone dwell time (s) |
| `CAMERA_INDEX` | `0` | Default camera device index |
| `TARGET_FPS` | `20` | Inference loop target FPS |

---

### `PPEDetector`

```python
from detector import PPEDetector

detector = PPEDetector(
    model_path="best.pt",       # optional; falls back to yolov8n.pt
    zone="work_at_height",      # default safety zone
)

annotated_frame, worker_states = detector.process_frame(frame, zone="construction")
detector.release()
```

`worker_states` is a list of dicts (see WebSocket worker object format above).

---

### `RuleEngine`

```python
from rule_engine import RuleEngine

engine = RuleEngine()
result = engine.evaluate(
    worker_id=101,
    detected_ppe={"helmet", "vest"},
    zone="construction",
    confidence=0.85,
)

print(result.compliant)     # False
print(result.missing_ppe)   # {"boots"}
```

---

### `TemporalValidator`

```python
from temporal_validator import TemporalValidator

validator = TemporalValidator()
should_alert, reason = validator.update(compliance_result)
```

---

### `VisionPipeline`

```python
from vision_pipeline import VisionPipeline

pipeline = VisionPipeline(zone="general_plant")
annotated, workers = pipeline.process_frame(frame)
pipeline.set_zone("work_at_height")
pipeline.release()
```
