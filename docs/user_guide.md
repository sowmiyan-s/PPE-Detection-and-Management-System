# EdgeVision PPE Compliance & Work-at-Height Platform — User Guide

## Overview
EdgeVision is an edge computer vision platform for real-time safety monitoring in industrial environments. It automatically detects workers, verifies PPE compliance (helmets, vests, boots, harnesses), validates zone rules, and records timestamped evidence of violations into MongoDB.

---

## Getting Started

### 1. Prerequisites
- **Python 3.10+**
- **Node.js 18+** & npm
- **MongoDB Atlas** or Local MongoDB instance
- Webcam / RTSP IP camera stream / YouTube video feed

### 2. Environment Setup
Create a `.env` file in the project root:
```env
MONGODB_URI=mongodb+srv://<username>:<password>@cluster.mongodb.net
MONGODB_DB_NAME=edgevision
TARGET_FPS=20
DETECTION_CONF=0.20
```

### 3. Running the Application
Launch both backend FastAPI server and Vite frontend using `start_fullstack.bat` or manually:
```bash
# Terminal 1: Python API & Vision Pipeline
python -m src.api.server

# Terminal 2: Web Dashboard Frontend
cd frontend
npm run dev
```

Open your browser at `http://localhost:5173`.

---

## Key Dashboard Pages

1. **Live Monitoring (`/live`)**: View live AI camera streams in multi-card grid view or single-feed focus view. Includes real-time detection filters (*Show All*, *Violations*, *Compliant*, *Wearing Helmet*, *Wearing Vest*).
2. **Active Violations (`/violations`)**: Review unacknowledged safety violations with high-resolution image snapshots and 5-second MP4 video evidence clips. Includes single-click **Acknowledge Alert** actions.
3. **Event History (`/events`)**: Complete searchable database log of past incidents with date range and zone filtering.
4. **Worker Compliance (`/compliance`)**: Aggregated compliance scores per worker tracking ID.
5. **Zone Configuration (`/zones`)**: Configure safety requirements per zone (*General Plant*, *Construction*, *Work at Height*, *Restricted Machinery*).
6. **Camera Management (`/cameras`)**: Add, edit, test, or remove RTSP streams, YouTube feeds, or local webcams.
7. **Model Monitoring (`/model`)**: Telemetry metrics including real-time FPS throughput, P95 latency, precision, recall, and mAP50.

---

## Jetson & Edge Deployment

### Exporting Model Engine
To export PyTorch weights (`.pt`) to ONNX or TensorRT:
```bash
# Export to ONNX format
python scripts/export_onnx.py --model experiments/ppe_training/custom_model/weights/best.pt

# Export to TensorRT FP16 Engine
python scripts/export_tensorrt.py --model experiments/ppe_training/custom_model/weights/best.pt --half
```

### Auto-boot Service Installation
Copy `scripts/edgevision.service` to `/etc/systemd/system/` on Linux:
```bash
sudo cp scripts/edgevision.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable edgevision
sudo systemctl start edgevision
```
