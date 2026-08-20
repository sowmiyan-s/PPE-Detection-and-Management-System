# 🚀 NVIDIA Jetson Edge Deployment Guide

> **Repository:** [https://github.com/Vidhyasree14/Cerberus-AI](https://github.com/Vidhyasree14/Cerberus-AI) | **Developer:** Vidhyashree M

Comprehensive deployment manual for running **Cerberus AI** on NVIDIA Jetson embedded hardware as a 24/7 industrial edge AI safety monitoring service.

---

## 📋 Recommended Hardware Specifications

| Component | Minimum Specification | Recommended Production Setup |
| :--- | :--- | :--- |
| **Edge Hardware** | NVIDIA Jetson Orin Nano (8 GB) | NVIDIA Jetson Orin NX (16 GB) / AGX Orin |
| **Operating System** | NVIDIA JetPack 6.0 (L4T R36.x / Ubuntu 22.04) | NVIDIA JetPack 6.1+ |
| **CUDA & TensorRT** | CUDA 12.2+ / TensorRT 10.x | CUDA 12.4+ / TensorRT 10.x |
| **Storage** | 64 GB NVMe SSD (M.2 Key-M) | 256 GB+ NVMe SSD |
| **Cooling** | Active Fan Heatsink | Industrial Enclosure with Active Fan |
| **Network** | 100 Mbps Ethernet | 1 Gbps Ethernet for multi-RTSP streams |
| **Camera Interfaces** | USB 3.0 / CSI-2 | PoE IP Camera switches via RTSP |

### Verified Jetson Modules

| Module | RAM | Max Cameras (5 FPS AI) | Recommended Use Case |
| :--- | :---: | :---: | :--- |
| **Jetson Orin Nano (8 GB)** | 8 GB LPDDR5 | 14 streams | Small to medium sites (≤ 14 cameras) |
| **Jetson Orin NX (16 GB)** | 16 GB LPDDR5 | 22 streams | Medium industrial sites (≤ 22 cameras) |
| **Jetson AGX Orin (32 GB)** | 32 GB LPDDR5 | 32+ streams | Large-scale plant floor monitoring |
| **Jetson AGX Orin (64 GB)** | 64 GB LPDDR5 | 50+ streams | Enterprise multi-building deployments |

---

## 🛠️ Step-by-Step Installation

### Step 1: System Package Provisioning

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
    python3-pip \
    python3-dev \
    libopencv-dev \
    build-essential \
    ffmpeg \
    git \
    curl

pip3 install --upgrade pip setuptools wheel
```

### Step 2: Clone Repository & Install Python Stack

```bash
git clone https://github.com/Vidhyasree14/Cerberus-AI.git /opt/cerberus-ai
cd /opt/cerberus-ai

pip3 install -r requirements.txt
```

> **Note:** PyTorch for Jetson must be installed from NVIDIA's Jetson-optimized wheel index, not PyPI. Check the Ultralytics Jetson guide for the correct wheel URL for your JetPack version.

### Step 3: Place Model Weights

```bash
# Copy your trained weights to the models directory
cp /path/to/best.pt /opt/cerberus-ai/models/best.pt
```

### Step 4: Compile Device-Specific TensorRT Engine

Build the TensorRT FP16 engine directly on the Jetson Orin GPU:

```bash
cd /opt/cerberus-ai
python3 scripts/export_tensorrt.py \
    --model models/best.pt \
    --imgsz 640 \
    --device 0
```

This produces `models/best.engine`, optimized specifically for the Jetson Ampere GPU architecture. This step typically takes **10–25 minutes** on first run.

### Step 5: System Performance & Power Mode Optimization

Lock clocks to maximum performance mode for sustained throughput:

```bash
# Set power mode to MAXN (Maximum performance — all cores at full clock)
sudo nvpmodel -m 0

# Lock CPU, GPU, and EMC memory frequencies
sudo jetson_clocks

# Verify current power mode and frequencies
sudo nvpmodel --query
sudo jetson_clocks --show
```

> **Power Modes Reference:**
> - `Mode 0 (MAXN)` — Maximum performance, ~15–25W TDP
> - `Mode 1` — Balanced, ~10W
> - `Mode 2` — Power saver, ~7W

### Step 6: Configure Automatic Systemd Daemon

Create the service file at `/etc/systemd/system/cerberus.service`:

```ini
[Unit]
Description=Cerberus AI Industrial Safety Telemetry Service
Documentation=https://github.com/Vidhyasree14/Cerberus-AI
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=jetson
Group=jetson
WorkingDirectory=/opt/cerberus-ai
ExecStart=/usr/bin/python3 -m src.api.server
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=cerberus-ai
Environment=PYTHONUNBUFFERED=1
Environment=CUDA_VISIBLE_DEVICES=0

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cerberus
sudo systemctl start cerberus

# Verify the service is running
sudo systemctl status cerberus
```

### Step 7: Monitor Service Logs

```bash
# Follow live logs
sudo journalctl -u cerberus -f

# View last 100 lines
sudo journalctl -u cerberus -n 100

# View logs since last boot
sudo journalctl -u cerberus -b
```

---

## 📡 Network Configuration for RTSP Multi-Camera

For high-density multi-camera deployments over RTSP:

```bash
# Increase socket buffer sizes for stable RTSP streams
sudo sysctl -w net.core.rmem_max=134217728
sudo sysctl -w net.core.wmem_max=134217728
sudo sysctl -w net.ipv4.tcp_rmem="4096 87380 134217728"
sudo sysctl -w net.ipv4.tcp_wmem="4096 87380 134217728"

# Persist across reboots
echo "net.core.rmem_max=134217728" | sudo tee -a /etc/sysctl.conf
echo "net.core.wmem_max=134217728" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

---

## 🌡️ Thermal Management

Install `jtop` for real-time Jetson system monitoring:

```bash
sudo pip3 install -U jetson-stats
sudo reboot

# After reboot
jtop
```

`jtop` provides live CPU/GPU/memory/temperature graphs and power consumption monitoring — the Jetson equivalent of `htop` + `nvidia-smi`.

---

## ✅ Post-Deployment Verification

```bash
# 1. Verify backend is responding
curl http://localhost:8000/api/model/benchmark | python3 -m json.tool

# 2. Check GPU is being used (should show device_type: "GPU")
curl http://localhost:8000/api/model/benchmark | grep device_type

# 3. Test WebSocket connectivity
python3 -c "
import asyncio, websockets, json
async def test():
    async with websockets.connect('ws://localhost:8000/ws') as ws:
        msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
        print('WebSocket OK:', json.loads(msg)['type'])
asyncio.run(test())
"
```

---

## 🔧 Troubleshooting

| Symptom | Likely Cause | Resolution |
| :--- | :--- | :--- |
| `CUDA out of memory` | Too many RTSP streams | Reduce camera count or switch to 3 FPS AI sampling |
| `TensorRT engine fails to load` | Engine compiled on different device | Recompile `best.engine` directly on this Jetson |
| `FPS drops below 15` | Not in MAXN power mode | Run `sudo nvpmodel -m 0 && sudo jetson_clocks` |
| `RTSP stream disconnects` | Network buffer too small | Apply sysctl socket buffer settings above |
| `Service fails to restart` | Python crash on startup | Check `journalctl -u cerberus -n 50` for traceback |

---

*Part of the [Cerberus AI](https://github.com/Vidhyasree14/Cerberus-AI) platform — developed by Vidhyashree M.*
