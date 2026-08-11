# 🛡️ EdgeVision — Autonomous Industrial PPE Safety & Compliance Intelligence Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-EE4C2C.svg?style=flat&logo=pytorch)](https://pytorch.org)
[![YOLOv8](https://img.shields.io/badge/YOLO-v8%20%2F%20v11-00FFFF.svg?style=flat)](https://ultralytics.com)
[![React](https://img.shields.io/badge/React-18+-61DAFB.svg?style=flat&logo=react)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6.svg?style=flat&logo=typescript)](https://www.typescriptlang.org)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.3+-38B2AC.svg?style=flat&logo=tailwindcss)](https://tailwindcss.com)

**EdgeVision** is an enterprise-grade, high-throughput autonomous computer vision system designed for real-time Personal Protective Equipment (PPE) compliance verification, worker tracking, and industrial safety telemetry across plant floors, construction zones, and high-hazard environments.

---

## 🌟 Key Features

* **⚡ Parallel Multi-Camera Vision Engine**: Runs asynchronous parallel YOLO inference threads across hardware webcams, RTSP streams, and YouTube Live links simultaneously.
* **🎥 YouTube Live & Stream Link Monitoring**: Directly streams YouTube live feeds or video links on-the-fly without downloading files or requiring user sign-in. Supports Netscape `cookies.txt` and mobile API fallback.
* **🎯 Custom Zone Rule Engine**: Per-zone granular PPE enforcement (`helmet`, `vest`, `boots`, `gloves`, `goggles`, `ear-mufs`, `face-guard`, `safety_belt`, `lanyard`, `hook`).
* **⏳ Temporal Compliance & Noise Suppression**: Multi-frame thresholding and minimum dwell-time verification suppress false single-frame alerts before raising real incident violations.
* **💾 Dual Storage Persistence**: Hybrid database engine (MongoDB Atlas cloud primary + local JSON disk fallback) ensuring zero data loss even during network disconnections.
* **📸 Automated Evidence Capture**: Asynchronously captures high-resolution violation snapshots and MP4 video clips without stalling live video FPS.
* **💻 High-Performance UI**: Modern, dark-mode React dashboard built with TanStack Router, Vite, and real-time WebSocket telemetry metrics.

---

## 📁 Repository Structure

```text
PPE DETECTION/
├── database/
│   ├── cameras_fallback.json    # Local JSON fallback store for camera configs
│   ├── zones_fallback.json      # Local JSON fallback store for zone rules
│   └── evidence/                # Violation JPEG snapshots & MP4 video clips
├── frontend/                    # React SPA Frontend (Vite + TanStack Router)
│   ├── src/
│   │   ├── components/         # Shared UI Shell & Layout components
│   │   ├── hooks/              # Custom hooks & session cache manager
│   │   ├── routes/             # Route views (Live, Cameras, Zones, Violations, Reports)
│   │   └── lib/                # Telemetry types & global DataContext provider
│   ├── package.json
│   └── vite.config.ts
├── models/                      # YOLO AI Model Weights (Tracked in GitHub)
│   ├── best.pt                  # Primary trained industrial PPE detection model
│   └── yolo11n.pt               # Fallback YOLO lightweight model
├── src/                         # Python Backend Engine
│   ├── api/
│   │   └── server.py           # FastAPI Application, WebSockets & REST API
│   ├── core/
│   │   ├── config.py           # System parameters & profiles
│   │   ├── db.py               # Hybrid MongoDB & local JSON persistence manager
│   │   ├── detector.py         # YOLO object detection wrapper
│   │   ├── rule_engine.py      # Spatial & zone compliance evaluator
│   │   └── temporal_validator.py# Multi-frame noise suppression
├── tests/                       # Unit test suite
├── start_fullstack.bat          # One-click startup script for Windows
├── requirements.txt             # Python dependencies
├── bytetrack.yaml               # ByteTrack multi-object tracking configuration
└── README.md
```

---

## 🚀 Quickstart Guide

### Prerequisites
* **Python**: 3.10 or higher
* **Node.js**: v18.0 or higher
* **Git** & **CUDA-compatible GPU** *(optional, CPU fallback supported)*

### 1. Clone & Install Backend Dependencies

```bash
git clone https://github.com/your-org/ppe-detection.git
cd "ppe-detection"

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python requirements
pip install -r requirements.txt
```

### 2. Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### 3. Run the Fullstack Application

#### Windows One-Click Launcher:
Double-click **`start_fullstack.bat`** or run in terminal:
```cmd
start_fullstack.bat
```

#### Manual Startup:
```bash
# Terminal 1: Backend Server (Port 8000)
python -m src.api.server

# Terminal 2: Frontend Dashboard (Port 3000)
cd frontend
npm run dev
```

Open your browser at **`http://localhost:3000`** to access the dashboard.

---

## 📡 REST API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `GET /api/cameras` | `GET` | Retrieve registered camera feeds & live pipeline status |
| `POST /api/cameras` | `POST` | Register a new webcam, RTSP, or YouTube stream feed |
| `POST /api/cameras/{id}/activate` | `POST` | Reconnect & initialize vision pipeline for target camera |
| `DELETE /api/cameras/{id}` | `DELETE` | Remove camera configuration from database |
| `GET /api/zones` | `GET` | List safety zones & enforced PPE requirements |
| `POST /api/zones` | `POST` | Create or update zone safety rules & PPE requirements |
| `GET /api/violations` | `GET` | Query historical incident logs & filter evidence media |
| `POST /api/violations/{id}/acknowledge` | `POST` | Acknowledge or decline violation incident |
| `GET /api/stats` | `GET` | Dashboard real-time telemetry summary |
| `GET /stream?camera_id={id}` | `GET` | Live MJPEG video stream with bounding boxes |
| `WS /ws` | `WS` | WebSocket endpoint for real-time annotated frame streaming |

---

## 📹 YouTube Live Stream & Video Setup

1. Navigate to **Camera Registry** (`/cameras`).
2. Click **`+ Register new camera / stream`**.
3. Select **Source Type**: `YouTube Video / Live Link`.
4. Paste the YouTube URL (e.g., `https://www.youtube.com/watch?v=...` or `https://youtu.be/...`).
5. Select target **Safety Zone** and click **`Add Camera & Connect Stream`**.

> **Note**: For age-restricted or protected feeds, place your Netscape-formatted `cookies.txt` file in the project root. The backend will automatically pass `"cookiefile": "cookies.txt"` to `yt_dlp`.

---

## 🔒 Environment Variables (`.env`)

```ini
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/?appName=Cluster0
MONGODB_DB_NAME=edgevision
MODEL_PATH=models/best.pt
DETECTION_CONF=0.20
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

---

## 📜 License & Compliance

Developed for enterprise workplace safety monitoring. Compliance rules adhere to OSHA and ISO 45001 occupational health and safety management guidelines.
