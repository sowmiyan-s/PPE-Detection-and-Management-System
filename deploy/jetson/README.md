# 🚀 EdgeVision - NVIDIA Jetson Orin Deployment & Demonstration Guide

> **Project:** Industrial PPE and Work-at-Height Safety Monitoring Platform  
> **Target Environment:** NVIDIA Jetson Orin (Orin Nano / Orin NX / AGX Orin)  
> **Operating System:** Linux Ubuntu 22.04 / 20.04 LTS (JetPack 5.1 / 6.0+ aarch64)  
> **Acceleration:** NVIDIA TensorRT (FP16 Engine) + DeepStream SDK / Hardware Codecs  

---

## 📋 System Overview & Architecture

EdgeVision is an industrial-grade edge AI safety compliance monitoring platform engineered for real-time inference on NVIDIA Jetson embedded platforms. It performs multi-class PPE detection (19 classes: hard hats, high-vis vests, safety boots, goggles, gloves, masks, harnesses, and safety lanyards), temporal dwell-time validation, and automated violation evidence recording.

```mermaid
flowchart LR
    A["Camera Inputs<br>(USB / CSI / RTSP / Video)"] --> B["NVIDIA GStreamer / V4L2<br>Hardware Decoder"]
    B --> C["YOLO + TensorRT FP16<br>(Ampere Tensor Cores)"]
    C --> D["ByteTrack + Re-ID<br>Worker Associator"]
    D --> E["Temporal Zone<br>Rule Engine"]
    E --> F["FastAPI Stream Hub<br>(0.0.0.0:8000 / WebSocket / MJPEG)"]
    E --> G["SQLite WAL DB &<br>Evidence Disk Storage"]
```

---

## ⚡ Hardware Support Matrix

| Jetson Module | Memory (LPDDR5) | TensorRT Inference FPS | Max Concurrent Streams (5 FPS AI) | Recommended Power Mode |
| :--- | :---: | :---: | :---: | :---: |
| **Jetson Orin Nano (8 GB)** | 8 GB Unified | **35–45 FPS** | **14 streams** | `nvpmodel -m 0` (15W MAXN) |
| **Jetson Orin NX (16 GB)** | 16 GB Unified | **55–75 FPS** | **22 streams** | `nvpmodel -m 0` (25W MAXN) |
| **Jetson AGX Orin (32/64 GB)** | 32 / 64 GB | **120+ FPS** | **50+ streams** | `nvpmodel -m 0` (50W/60W MAXN) |

---

## 🛠️ Fast 3-Step Setup on Jetson Orin

### Step 1: Clone Repository & Run Automated Provisioning
```bash
git clone https://github.com/sowmiyan-s/PPE-Detection-and-Management-System.git /opt/edgevision
cd /opt/edgevision

# Run automated system setup (installs V4L2, GStreamer, Python stack, and locks GPU clocks)
chmod +x deploy/jetson/*.sh
./deploy/jetson/install.sh
```

### Step 2: Compile TensorRT FP16 Engine
Compile the YOLO PyTorch model directly on the Jetson Orin Ampere GPU for maximum acceleration:
```bash
./deploy/jetson/export_engine.sh
```
> **Note:** This generates `models/best.engine`. TensorRT engines are device-specific and utilize Jetson Tensor Cores for sub-15ms inference latency.

### Step 3: Launch Application Server
```bash
./deploy/jetson/start.sh
```
The server binds to `http://0.0.0.0:8000` and is accessible across the local network.

---

## 🎥 Demonstration Workflows

### 1. Interactive Web Dashboard & Live Stream
Open a browser on any workstation on the same network or on the Jetson display:
- **Web UI & Streaming Dashboard:** `http://<JETSON_IP>:8000`
- **Live Annotated MJPEG Stream:** `http://<JETSON_IP>:8000/api/stream`
- **Real-Time WebSocket Stream:** `ws://<JETSON_IP>:8000/ws`
- **Hardware Telemetry Endpoint:** `http://<JETSON_IP>:8000/api/device/metrics`

---

### 2. Live Camera / Video CLI Demonstration
Use `./deploy/jetson/run_demo.sh` to run the detection and tracking pipeline on any camera source:

```bash
# Option A: USB Webcam (/dev/video0)
./deploy/jetson/run_demo.sh --source 0

# Option B: Jetson MIPI CSI Camera (IMX219 / IMX477 / Raspberry Pi HQ Camera)
./deploy/jetson/run_demo.sh --source csi://0

# Option C: Bundled Offline Sample Test Video (No camera required!)
./deploy/jetson/run_demo.sh --source sample

# Option D: IP RTSP Industrial Camera
./deploy/jetson/run_demo.sh --source rtsp://admin:password@192.168.1.100:554/stream1

# Option E: Display GUI window on attached HDMI/DisplayPort monitor
./deploy/jetson/run_demo.sh --source 0 --display
```

---

### 3. Hardware-Accelerated DeepStream GStreamer Pipeline
For high-throughput industrial deployments:
```bash
# Run DeepStream pipeline with hardware decoding and ByteTrack tracking:
python3 deploy/jetson/deepstream_pipeline.py --input 0
```

---

### 4. Run Edge Hardware Benchmark
Measure exact latency percentiles (P50, P95, P99), aggregate FPS, GPU VRAM, and SoC temperature:
```bash
./deploy/jetson/run_benchmark.sh
```

Example expected output:
```text
============================================================
             📊 JETSON ORIN BENCHMARK RESULTS
============================================================
 Hardware Device        : NVIDIA Jetson Orin (nvgpu)
 SoC Temperature        : 44.5°C
 CPU Utilization        : 18.2%
 RAM Memory Used        : 3.42 GB / 7.64 GB (44.8%)
 GPU VRAM Allocated     : 420.5 MB (Reserved: 580.0 MB)
------------------------------------------------------------
 Average Inference Time : 12.80 ms
 P50 (Median) Latency   : 12.40 ms
 P95 Inference Latency  : 14.10 ms
 P99 Inference Latency  : 15.60 ms
 Aggregate Throughput   : 78.1 FPS
------------------------------------------------------------
 Status: 🟢 EXCELLENT - Exceeds 30 FPS Real-Time Baseline
============================================================
```

---

### 5. 24/7 Background Systemd Service
To enable EdgeVision as an automatic system service that starts on boot:
```bash
sudo cp deploy/jetson/edgevision-pipeline.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable edgevision-pipeline.service
sudo systemctl start edgevision-pipeline.service

# Check service status and logs
sudo systemctl status edgevision-pipeline.service
sudo journalctl -u edgevision-pipeline -f
```

---

## 🧪 Verification & Health Check Commands

```bash
# 1. Health & Pipeline Status
curl -s http://localhost:8000/api/health | python3 -m json.tool

# 2. Hardware Telemetry & Capacity Metrics
curl -s http://localhost:8000/api/device/metrics | python3 -m json.tool

# 3. List Configured Safety Zones & Active PPE Rules
curl -s http://localhost:8000/api/zones | python3 -m json.tool

# 4. Query Recent Compliance Violations
curl -s http://localhost:8000/api/violations | python3 -m json.tool

# 5. Live Jetson System Monitoring (jtop)
jtop
```

---

## 🔧 Troubleshooting & Jetson FAQs

| Symptom | Probable Cause | Recommended Resolution |
| :--- | :--- | :--- |
| **`CUDA out of memory`** | Excessively high batch size or input resolution | Set `INFERENCE_IMG_SIZE=480` in `.env` or reduce concurrent camera streams. |
| **`TensorRT engine failed to load`** | Engine was compiled on a different GPU architecture | Recompile locally using `./deploy/jetson/export_engine.sh`. |
| **`CSI camera not opening`** | `nvargus-daemon` service lockup | Run `sudo systemctl restart nvargus-daemon`. |
| **`FPS lower than expected`** | Device in low power profile | Run `sudo nvpmodel -m 0 && sudo jetson_clocks`. |
| **`V4L2 camera cannot open /dev/video0`** | User permissions missing | Run `sudo usermod -aG video $USER` and re-login. |

---

*Part of the **EdgeVision / Cerberus AI** Safety Platform.*
