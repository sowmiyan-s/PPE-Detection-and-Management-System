# EdgeVision PPE Platform – Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     EdgeVision PPE Platform                         │
│                                                                     │
│  ┌───────────┐    ┌─────────────────────────────────────────────┐  │
│  │  Camera   │───▶│           Vision Pipeline                   │  │
│  │  (RTSP /  │    │                                             │  │
│  │  USB /    │    │  ┌──────────┐  ┌──────────┐  ┌──────────┐  │  │
│  │  File)    │    │  │ Stage 1  │  │ Stage 2  │  │ Stage 3  │  │  │
│  └───────────┘    │  │ Person   │─▶│   PPE    │─▶│ Person-  │  │  │
│                   │  │Detection │  │Detection │  │  PPE     │  │  │
│                   │  │& Tracking│  │(8 class) │  │  Assoc.  │  │  │
│  ┌───────────┐    │  │ByteTrack │  │  YOLO    │  │ Body-    │  │  │
│  │  Image    │───▶│  └──────────┘  └──────────┘  │ Region   │  │  │
│  │ Enhancer  │    │                               └──────────┘  │  │
│  │ (CLAHE+   │    │  ┌──────────┐  ┌──────────┐               │  │
│  │  sharpen) │    │  │ Stage 4  │  │ Stage 5  │               │  │
│  └───────────┘    │  │  Rule    │─▶│ Temporal │               │  │
│                   │  │  Engine  │  │Validator │               │  │
│                   │  │ (Zones)  │  │(8/10 wnd)│               │  │
│                   │  └──────────┘  └────┬─────┘               │  │
│                   └────────────────────┬┘─────────────────────┘  │
│                                        │                           │
│                         ┌─────────────▼──────────────┐            │
│                         │      Alert Decision         │            │
│                         │  (conf ≥ 0.30, zone ≥ 2s,  │            │
│                         │   8/10 frames violated)    │            │
│                         └──────┬────────────┬─────────┘            │
│                                │            │                       │
│                   ┌────────────▼──┐   ┌─────▼──────────┐           │
│                   │  MQTT Broker  │   │  WebSocket /   │           │
│                   │ (violations)  │   │  Annotated     │           │
│                   └──────┬────────┘   │  Frame Stream  │           │
│                          │            └─────┬──────────┘           │
└──────────────────────────┼─────────────────┼────────────────────── ┘
                           │                 │
          ┌────────────────▼──────────────────▼──────────────────┐
          │              Web Application (Streamlit / FastAPI)     │
          │                                                        │
          │  ┌──────────────┐  ┌────────────────┐  ┌──────────┐  │
          │  │    Live      │  │   Violations   │  │  Reports │  │
          │  │  Monitoring  │  │  & History     │  │ & Stats  │  │
          │  └──────────────┘  └────────────────┘  └──────────┘  │
          │  ┌──────────────┐  ┌────────────────┐  ┌──────────┐  │
          │  │   Worker     │  │     Zone       │  │  Model   │  │
          │  │  Compliance  │  │ Configuration  │  │Monitoring│  │
          │  └──────────────┘  └────────────────┘  └──────────┘  │
          └───────────────────────────┬───────────────────────────┘
                                      │
                         ┌────────────▼──────────┐
                         │     PostgreSQL DB      │
                         │  cameras / zones /     │
                         │  violation_events /    │
                         │  worker_tracks / …     │
                         └───────────────────────┘
```

---

## Component Map

| Component | File(s) | Purpose |
|-----------|---------|---------|
| Stage 1 – Person detection & tracking | `detector.py`, `vision_pipeline.py` | YOLOv8 + ByteTrack |
| Stage 2 – PPE detection | `detector.py` | 8-class YOLO model |
| Stage 3 – Association | `association.py` | Body-region + containment |
| Stage 4 – Rule engine | `rule_engine.py` | Zone-based PPE requirements |
| Stage 5 – Temporal validation | `temporal_validator.py` | 8/10 frame window |
| Alert publishing | `publisher.py` | MQTT + temporal gating |
| Image enhancement | `enhancer.py` | CLAHE + bilateral + sharpen |
| Streamlit dashboard | `app.py` | 8-page multi-view UI |
| WebSocket API server | `server.py` | FastAPI + live stream |
| Central config | `config.py` | All tunable parameters |
| Training | `train_model.py` | YOLOv8 fine-tuning |
| ONNX export | `export_onnx.py` | Portable model format |
| TensorRT export | `export_tensorrt.py` | Jetson edge deployment |
| Database schema | `database/schema.sql` | PostgreSQL tables |
| Tests | `tests/` | Unit and integration tests |

---

## Inference Pipeline (per frame)

```
Camera frame
     │
     ▼
IndustrialImageEnhancer.enhance()
     │  CLAHE (low-light) + bilateral (noise) + sharpen (blur)
     ▼
YOLO.track(persist=True, tracker="bytetrack.yaml")
     │  Returns bounding boxes + class IDs + tracking IDs
     ├─ class == "person"  ──────────────────────────┐
     └─ class in PPE_CLASSES ─────────────────────┐  │
                                                  ▼  ▼
                              associate_ppe_to_persons()
                                  │  Body-region containment
                                  │  Nearest-person fallback
                                  ▼
                        per-worker detected_ppe set
                                  │
                                  ▼
                        RuleEngine.evaluate()
                            │  Zone PPE requirements
                            │  Returns ComplianceResult
                            ▼
                   TemporalValidator.update()
                            │  8/10 frames, conf, zone dwell
                            │
                   ┌────────┴────────┐
                  No                Yes
                   │                 │
               suppress          publish MQTT
                                  alert
```

---

## Deployment Architecture (Jetson Edge)

```
      Site Camera (1080p @ 30fps)
              │
              ▼
     Jetson Orin / AGX Xavier
     ┌─────────────────────────┐
     │  TensorRT FP16 Engine   │  ← best.engine (device-specific)
     │  VisionPipeline         │
     │  systemd: ppe_monitor   │
     └────────┬────────────────┘
              │  MQTT over TLS
              ▼
     Private MQTT Broker
     (HiveMQ Cloud / Mosquitto)
              │
              ▼
     Cloud / On-premise Server
     ┌─────────────────────────┐
     │  Streamlit Dashboard    │
     │  FastAPI WebSocket API  │
     │  PostgreSQL Database    │
     └─────────────────────────┘
```
