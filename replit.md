# EdgeVision PPE Compliance and Work-at-Height Safety Platform

A full-stack industrial safety monitoring system using AI/ML and edge computer
vision to detect PPE compliance in real time.

## Stack

- **Python 3.12**
- **YOLOv8** (`ultralytics`) — 8-class PPE object detection
- **ByteTrack** — multi-object person tracking
- **Streamlit** (`app.py`) — 8-page dashboard UI
- **FastAPI + WebSockets** (`server.py`) — live annotated video stream
- **OpenCV** — frame capture, enhancement, annotation
- **paho-mqtt** — MQTT alert publishing
- **PostgreSQL** (optional) — event persistence

## Architecture: 5-Stage Vision Pipeline

| Stage | Module | Purpose |
|-------|--------|---------|
| 1 | `detector.py`, `vision_pipeline.py` | Person detection + ByteTrack tracking |
| 2 | `detector.py` | 8-class PPE detection |
| 3 | `association.py` | Body-region person-to-PPE association |
| 4 | `rule_engine.py` | Zone-based PPE rule evaluation |
| 5 | `temporal_validator.py` | 8/10 frame window anti-false-alarm |

## Key Files

| File | Purpose |
|------|---------|
| `config.py` | All tunable parameters (MQTT, model, zones, FPS) |
| `app.py` | Streamlit multi-page dashboard |
| `server.py` | FastAPI WebSocket live-stream server |
| `detector.py` | Full pipeline runner (Stages 1–5) |
| `association.py` | PPE-to-person body-region matching |
| `rule_engine.py` | Zone rule engine (Stage 4) |
| `temporal_validator.py` | Temporal alert gating (Stage 5) |
| `publisher.py` | MQTT publisher with temporal validation |
| `enhancer.py` | CLAHE + bilateral + sharpen pre-processing |
| `train_model.py` | YOLOv8 fine-tuning script |
| `export_onnx.py` | Export trained model to ONNX |
| `export_tensorrt.py` | Export to TensorRT FP16 engine (Jetson) |
| `database/schema.sql` | PostgreSQL schema (16 tables) |
| `dataset.yaml` | YOLOv8 dataset config (8 PPE classes) |
| `tests/` | Unit tests (pytest) |
| `docs/` | API docs, dataset guide, Jetson setup, user guide |
| `jetson/` | systemd service files for edge deployment |

## PPE Classes

`person`, `helmet`, `vest`, `boots`, `safety_belt`, `lanyard`, `hook`, `anchor_point`

## Safety Zones

| Zone | Required PPE |
|------|-------------|
| General plant | helmet, vest |
| Construction | helmet, vest, boots |
| Work at height | helmet, vest, boots, safety_belt, hook |
| Restricted machinery | helmet, vest |

## Running Locally

### Streamlit Dashboard
```bash
streamlit run app.py
```

### FastAPI WebSocket Server
```bash
python server.py
```

### Run Tests
```bash
pytest tests/ -v
```

### Train Custom Model
```bash
python train_model.py --epochs 150 --imgsz 640
```

### Export to ONNX
```bash
python export_onnx.py --model ppe_training/custom_model/weights/best.pt
```

### Export to TensorRT (Jetson only)
```bash
python export_tensorrt.py --model ppe_training/custom_model/weights/best.pt
```

## Configuration (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `MQTT_BROKER` | `test.mosquitto.org` | MQTT broker hostname |
| `MQTT_PORT` | `1883` | MQTT port |
| `MQTT_TOPIC` | `factory/ppe_violations` | Alert topic |
| `MQTT_USERNAME` | `` | MQTT auth username |
| `MQTT_PASSWORD` | `` | MQTT auth password |
| `MQTT_USE_TLS` | `false` | Enable TLS |
| `MODEL_PATH` | `ppe_training/custom_model/weights/best.pt` | YOLO weights |
| `DETECTION_CONF` | `0.20` | Min detection confidence |
| `TEMPORAL_WINDOW` | `10` | Frames in sliding window |
| `TEMPORAL_MIN_HITS` | `8` | Violation frames needed |
| `TEMPORAL_MIN_CONF` | `0.30` | Min confidence for alert |
| `TEMPORAL_MIN_ZONE_SECS` | `2.0` | Min zone dwell time (s) |
| `CAMERA_INDEX` | `0` | Default camera device |
| `TARGET_FPS` | `20` | Inference target FPS |

## External Dependencies

- **MQTT Broker**: defaults to `test.mosquitto.org` (public). Replace via `MQTT_BROKER` for production.
- **Camera**: webcam, RTSP stream, or video file via OpenCV.
- **PostgreSQL**: optional, for persisting violation events (see `database/schema.sql`).

## Jetson Edge Deployment

See `docs/jetson_setup.md` for full installation and startup service configuration.
Deploy pipeline: train → ONNX → TensorRT FP16 → DeepStream (optional).

## User Preferences

_None recorded yet._
hello
