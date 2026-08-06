# Jetson Installation and Startup Service Guide

## Verified Configuration

| Component | Version |
|-----------|---------|
| Hardware | NVIDIA Jetson Orin / AGX Xavier |
| JetPack | 6.x (L4T R36) |
| CUDA | 12.2 |
| TensorRT | 10.x |
| Python | 3.10 |
| DeepStream | 9.1 (optional) |

---

## Step 1 – Flash JetPack

Use NVIDIA SDK Manager on a host Ubuntu machine to flash the Jetson:

```
https://developer.nvidia.com/sdk-manager
```

Select the matching JetPack version for your hardware.  After flashing,
confirm the versions:
```bash
cat /etc/nv_tegra_release
nvcc --version
```

---

## Step 2 – Install Python dependencies

```bash
sudo apt update && sudo apt install -y python3-pip python3-dev libopencv-dev
pip3 install --upgrade pip

# Install Ultralytics (installs PyTorch for Jetson automatically)
pip3 install ultralytics

# Install remaining project dependencies
pip3 install -r requirements.txt
```

> **Note:** On Jetson, always use the NVIDIA-provided PyTorch wheel, not pip's
> default x86 wheel.  Ultralytics handles this automatically when run on
> L4T (ARM64).

---

## Step 3 – Clone or copy the project

```bash
git clone https://github.com/sowmiyan-s/test-repo.git /opt/ppe_monitor
cd /opt/ppe_monitor
```

---

## Step 4 – Copy model weights

```bash
scp user@dev-machine:ppe_training/custom_model/weights/best.pt \
    /opt/ppe_monitor/ppe_training/custom_model/weights/

scp user@dev-machine:ppe_training/custom_model/weights/best.onnx \
    /opt/ppe_monitor/ppe_training/custom_model/weights/
```

Then build the TensorRT engine on the Jetson (see `docs/tensorrt_instructions.md`):
```bash
cd /opt/ppe_monitor
python3 export_tensorrt.py --model ppe_training/custom_model/weights/best.pt
```

---

## Step 5 – Configure environment

Create `/opt/ppe_monitor/.env`:
```ini
# MQTT
MQTT_BROKER=your.private.broker.com
MQTT_PORT=8883
MQTT_TOPIC=factory/ppe_violations
MQTT_USERNAME=ppe_service
MQTT_PASSWORD=<secret>
MQTT_USE_TLS=true

# Model
MODEL_PATH=/opt/ppe_monitor/ppe_training/custom_model/weights/best.engine
DETECTION_CONF=0.25
TARGET_FPS=20

# Camera
CAMERA_INDEX=0
FRAME_WIDTH=1920
FRAME_HEIGHT=1080

# Zone
DEFAULT_ZONE=work_at_height
```

Restrict permissions:
```bash
chmod 600 /opt/ppe_monitor/.env
```

---

## Step 6 – Install systemd service

The service file is at `jetson/ppe_monitor.service`.

```bash
sudo cp /opt/ppe_monitor/jetson/ppe_monitor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ppe_monitor
sudo systemctl start ppe_monitor
```

Check status:
```bash
sudo systemctl status ppe_monitor
sudo journalctl -u ppe_monitor -f
```

---

## Step 7 – Power mode optimisation

For sustained inference, set the Jetson to maximum performance mode:
```bash
sudo nvpmodel -m 0      # MAXN (all cores, maximum power)
sudo jetson_clocks      # lock clocks to maximum
```

For balanced operation:
```bash
sudo nvpmodel -m 2      # 15W mode (Orin)
```

Check current mode:
```bash
sudo nvpmodel -q
```

---

## Monitoring on Jetson

```bash
# GPU/CPU/memory/temperature
sudo tegrastats

# Real-time stats (requires jetson-stats)
pip3 install jetson-stats
sudo jtop
```

---

## Updating the model

1. Copy new `best.pt` and `best.onnx` to `/opt/ppe_monitor/ppe_training/custom_model/weights/`
2. Rebuild the TensorRT engine: `python3 export_tensorrt.py`
3. Restart the service: `sudo systemctl restart ppe_monitor`
