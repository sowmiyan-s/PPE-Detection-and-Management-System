# 🚀 NVIDIA Jetson Edge Deployment Guide

Comprehensive deployment manual for running **Cerberus AI** on NVIDIA Jetson embedded hardware (Jetson Orin Nano, Jetson Orin NX, Jetson AGX Orin, and Jetson Xavier).

---

## 📋 Recommended Hardware Specifications

| Component | Minimum Specification | Recommended Production Setup |
| :--- | :--- | :--- |
| **Edge Hardware** | NVIDIA Jetson Orin Nano (8 GB) | NVIDIA Jetson Orin NX (16 GB) / AGX Orin |
| **Operating System** | NVIDIA JetPack 6.0 (L4T R36.x / Ubuntu 22.04) | NVIDIA JetPack 6.1+ |
| **CUDA & TensorRT** | CUDA 12.2+ / TensorRT 10.x | CUDA 12.4+ / TensorRT 10.x |
| **Storage** | 64 GB NVMe SSD (M.2 Key-M) | 256 GB+ NVMe SSD |
| **Cooling** | Active Fan Heatsink | Industrial Enclosure with Active Fan |

---

## 🛠️ Step-by-Step Installation

### Step 1: System Package Provisioning
```bash
sudo apt update && sudo apt install -y \
    python3-pip \
    python3-dev \
    libopencv-dev \
    build-essential \
    ffmpeg

pip3 install --upgrade pip setuptools wheel
```

### Step 2: Clone Repository & Install Python Stack
```bash
git clone https://github.com/sowmiyan-s/ppe-detection-yolo.git /opt/cerberus-ai
cd /opt/cerberus-ai

pip3 install -r requirements.txt
```

### Step 3: Compile Device-Specific TensorRT Engine
Build the TensorRT FP16 engine directly on the Jetson Orin GPU:
```bash
python3 scripts/export_tensorrt.py \
    --model models/best.pt \
    --imgsz 640 \
    --device 0
```
This produces `models/best.engine`, optimized specifically for the Jetson Ampere/Volta architecture.

### Step 4: System Performance & Power Mode Optimization
Lock clocks to maximum performance mode:
```bash
# Set power mode to MAXN (Maximum performance)
sudo nvpmodel -m 0

# Lock CPU, GPU, and EMC memory frequencies
sudo jetson_clocks
```

### Step 5: Configure Automatic Systemd Daemon
Create `/etc/systemd/system/cerberus.service`:
```ini
[Unit]
Description=Cerberus AI Industrial Safety Telemetry Service
After=network.target

[Service]
Type=simple
User=jetson
WorkingDirectory=/opt/cerberus-ai
ExecStart=/usr/bin/python3 -m src.api.server
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable cerberus
sudo systemctl start cerberus
sudo systemctl status cerberus
```
