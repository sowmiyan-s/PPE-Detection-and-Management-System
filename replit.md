# PPE Compliance Monitoring System

A real-time worker safety monitoring system that uses YOLOv8 computer vision to detect Personal Protective Equipment (PPE) compliance on a factory/job site floor.

## Stack

- **Python 3.12**
- **YOLOv8** (`ultralytics`) — object detection model for PPE items (hard hats, vests, etc.)
- **Streamlit** (`app.py`) — dashboard UI with MQTT-driven live alerts
- **FastAPI + WebSockets** (`server.py`) — live video streaming API
- **OpenCV** — video capture and frame processing
- **paho-mqtt** — MQTT broker integration for publishing/subscribing to PPE violation events

## Key Files

| File | Purpose |
|------|---------|
| `app.py` | Streamlit dashboard — real-time PPE compliance UI |
| `server.py` | FastAPI WebSocket server — streams annotated video frames |
| `detector.py` | YOLOv8 PPE detection logic |
| `vision_pipeline.py` | Full inference pipeline (capture → detect → track → publish) |
| `enhancer.py` | Frame pre-processing / image enhancement |
| `association.py` | Multi-object tracking / person association |
| `publisher.py` | MQTT event publisher for violations |
| `train_model.py` | Custom model training script |
| `dataset.yaml` | YOLOv8 dataset config for the PPE dataset |
| `yolov8n.pt` | Pre-trained YOLOv8 nano weights |

## Running the App

### Streamlit Dashboard
```bash
streamlit run app.py
```

### FastAPI Video Server
```bash
python server.py
```

## External Dependencies

- **MQTT Broker**: connects to `test.mosquitto.org:1883` (public test broker) on topic `factory/ppe_violations`
- **Camera**: expects a webcam or video source accessible via OpenCV

## User Preferences

_None recorded yet._
