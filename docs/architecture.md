# 🏗️ Cerberus AI — System Architecture & Pipeline Design

> **Repository:** [https://github.com/Vidhyasree14/Cerberus-AI](https://github.com/Vidhyasree14/Cerberus-AI) | **Developer:** Vidhyashree M

Cerberus AI is an industrial edge computer vision platform architected for resilient, multi-camera PPE compliance monitoring. The platform processes continuous video streams through a modular 5-stage inference and temporal verification pipeline, serving low-latency telemetry to a React control room dashboard via FastAPI WebSockets.

---

## 📐 High-Level Architecture

```mermaid
flowchart TD
    subgraph INGESTION["1. Input Ingestion Layer"]
        C1["RTSP / IP Cameras"]
        C2["Local USB Webcams"]
        C3["HTTP / MP4 / YouTube Feeds"]
        TG["Threaded Frame Grabber<br>(Non-Blocking Ring Buffer)"]
        C1 --> TG
        C2 --> TG
        C3 --> TG
    end

    subgraph VISION["2. 5-Stage Vision Pipeline"]
        S1["Stage 1: Person Tracking<br>(ByteTrack ID Persistence)"]
        S2["Stage 2: Multi-Class Detection<br>(YOLOv8 FP16 / TensorRT)"]
        S3["Stage 3: Spatial Association<br>(Anatomical Region Mapping)"]
        S4["Stage 4: Per-Zone Rule Engine<br>(Configurable Safety Requirements)"]
        S5["Stage 5: Temporal Validator<br>(≥ 8/10 Window & 2s Dwell Floor)"]

        TG --> S1
        S1 --> S2
        S2 --> S3
        S3 --> S4
        S4 --> S5
    end

    subgraph ASYNC_CORE["3. Asynchronous Core & Persistence"]
        DB[("SQLite WAL Database<br>(Async In-Memory Cache)")]
        EVI["Async Evidence Writer<br>(Snapshot JPEGs & MP4 Clips)"]
        WS_HUB["WebSocket Broadcast Hub<br>(/ws)"]

        S5 --> DB
        S5 --> EVI
        S5 --> WS_HUB
    end

    subgraph PRESENTATION["4. Presentation Layer"]
        UI["React 19 Executive Dashboard<br>(TanStack Start / Recharts)"]
        WS_HUB --> UI
        DB --> UI
    end
```

---

## 🧩 Deep Dive: Pipeline Stage-by-Stage

### Stage 1 — Ingestion & Resilient Frame Acquisition (`ThreadedCamera`)

Each camera feed runs as an isolated daemon thread, completely decoupling slow network I/O from GPU inference. Key mechanisms:

| Feature | Description |
| :--- | :--- |
| **Non-Blocking Ring Buffer** | Maintains a fixed-size frame buffer; oldest frames are dropped if inference falls behind |
| **Auto-Recovery Loop** | Automatically handles RTSP packet loss, socket resets, and stream stalls with exponential backoff |
| **Adaptive Frame Rate Decimation** | Implements dynamic frame skipping when GPU or CPU load increases, preserving smooth throughput |
| **Source Support** | USB webcam index, RTSP/RTMP URLs, HTTP MJPEG streams, local MP4 files, YouTube Live URLs |

### Stage 2 — Person Tracking (`ByteTrack`)

ByteTrack provides persistent `Worker-ID` assignment across consecutive frames using:
- **Kalman Filter Motion Prediction:** Predicts worker positions across frames even during brief occlusions.
- **IoU-Based Bounding Box Association:** Associates new detections to existing track IDs using intersection-over-union similarity.
- **Re-ID Recovery:** Recovers previously lost tracks when a worker re-enters the frame after obstruction.

```
Frame N:   Worker-101 [at position A] → ByteTrack → Worker-101 [persistent]
Frame N+5: Worker-101 [occluded]      → ByteTrack → Worker-101 [interpolated]
Frame N+8: Worker-101 [re-visible]    → ByteTrack → Worker-101 [recovered]
```

### Stage 3 — Multi-Class PPE Detection (`YOLOv8`)

- Evaluates full frames and worker-cropped ROIs across **19 industrial object and violation classes**.
- Supports both native **PyTorch FP32/FP16** execution and compiled **TensorRT engines** for sub-15 ms inference latency.
- The model is trained to detect both compliant PPE states (e.g., `Hard_hat`) and explicit violation states (e.g., `No-Helmet`), enabling cross-referenced confidence scoring.

### Stage 4 — Anatomical Spatial Association

Maps detected PPE items to specific worker bounding boxes using body-region anatomical heuristics:

| Body Region | Vertical Proportion | Associated PPE Classes |
| :--- | :---: | :--- |
| **Head Region** | `0.0 – 0.28 × height` | `Hard_hat`, `Mask`, `Glass`, `Ear-Protection` |
| **Torso Region** | `0.25 – 0.65 × height` | `Vest`, Safety Harness |
| **Lower Body / Feet** | `0.65 – 1.0 × height` | `Boots`, `Glove` |

Cross-references positive detections (e.g., `Hard_hat`) against negative states (`No-Helmet`) to produce a definitive per-worker compliance verdict.

### Stage 5 — Per-Zone Rule Engine (`RuleEngine`)

Configurable per-zone compliance matrices define the exact PPE requirements for each operational area:

| Zone Type | Example Required PPE |
| :--- | :--- |
| **General Plant Floor** | `Hard_hat`, `Vest` |
| **Construction Zone** | `Hard_hat`, `Vest`, `Boots`, `Glass` |
| **Work at Height** | `Hard_hat`, `Vest`, `Boots`, `Fire_prevention_Net` |
| **Machinery Floor** | `Hard_hat`, `Vest`, `Ear-Protection`, `Glass` |

### Stage 6 — Temporal Noise Suppression (`TemporalValidator`)

Prevents false alarms caused by lighting glare, transient viewing angles, or brief occlusions:

```
Violation Candidate Timeline:
Frame:   1  2  3  4  5  6  7  8  9  10
State:   V  V  -  V  V  V  V  V  V  V   (V = violation detected, - = not detected)
Count:   8/10 detections = ALERT TRIGGERED ✅

Frame:   1  2  3  4  5  6  7  8  9  10
State:   V  V  -  -  V  -  V  -  V  -   (5/10 — noise suppressed)
Count:   5/10 detections = SUPPRESSED ✗
```

- Requires ≥ **8 out of 10** consecutive frame detections before triggering a formal alert.
- Enforces a minimum **2-second dwell time** before committing violation evidence to the database.

---

## ⚡ Concurrency & Thread Isolation Model

Cerberus AI uses separated `ThreadPoolExecutors` to guarantee disk operations and database writes never starve live inference:

| Executor | Pool Size | Responsibilities |
| :--- | :---: | :--- |
| **`_INFER_EXECUTOR`** | 2–4 workers | YOLOv8 forward passes, ByteTrack state updates |
| **`_IO_EXECUTOR`** | 4–8 workers | JPEG encoding, MP4 evidence generation, database writes |

```
[Camera Stream 1] ───┐
[Camera Stream 2] ───┼──► [_INFER_EXECUTOR] ──► Real-time Detections & Tracking
[Camera Stream N] ───┘                                │
                                                       ▼
                                              [_IO_EXECUTOR] ──► Disk / DB / Evidence
```

---

## 🗄️ Data Flow & Persistence

```mermaid
sequenceDiagram
    participant CAM as Camera Thread
    participant PIPE as Vision Pipeline
    participant TEMP as Temporal Validator
    participant DB as SQLite WAL DB
    participant WS as WebSocket Hub
    participant UI as React Dashboard

    CAM->>PIPE: Raw video frame
    PIPE->>TEMP: Violation candidate + worker state
    TEMP->>DB: Write confirmed violation + evidence snapshot
    TEMP->>WS: Broadcast live telemetry frame
    WS->>UI: JSON worker state payload
    UI->>DB: REST fetch for scorecards & history
```

---

## 🧱 Module Reference

| Module | File | Responsibility |
| :--- | :--- | :--- |
| Frame Grabber | `src/core/detector.py` | Multi-source threaded video acquisition |
| Vision Orchestrator | `src/core/vision_pipeline.py` | 5-stage pipeline coordinator |
| Worker Tracker | `src/core/worker_tracker.py` | ByteTrack ID management & trajectory |
| Rule Engine | `src/core/rule_engine.py` | Per-zone PPE compliance matrix evaluation |
| Temporal Validator | `src/core/temporal_validator.py` | Sliding-window false-alarm suppression |
| Spatial Associator | `src/core/association.py` | Anatomical PPE-to-worker mapping |
| Database Layer | `src/core/db.py` + `sqlite_db.py` | Async WAL persistence & query cache |
| Hardware Telemetry | `src/core/device_telemetry.py` | CPU / RAM / GPU / Jetson metrics |
| WebSocket Publisher | `src/core/publisher.py` | Live broadcast hub for React dashboard |
| FastAPI Server | `src/api/server.py` | REST endpoints + WebSocket `/ws` |

---

*Part of the [Cerberus AI](https://github.com/Vidhyasree14/Cerberus-AI) platform — developed by Vidhyashree M.*
