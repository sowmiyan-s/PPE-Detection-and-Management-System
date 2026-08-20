#!/usr/bin/env bash
# EdgeVision NVIDIA Jetson Orin / DeepStream 9.1 Automated Installation Script

set -e

echo "=== EdgeVision Jetson Orin Deployment Setup ==="

# 1. Update APT Package Index
sudo apt-get update
sudo apt-get install -y python3-pip python3-dev build-essential libopencv-dev ffmpeg git systemd python3-gi gir1.2-gstreamer-1.0 libgirepository1.0-dev

# 2. Upgrade Pip and PyTorch Dependencies
python3 -m pip install --upgrade pip setuptools wheel

# 3. Install Required Python Packages
pip3 install -r requirements.txt

# 4. Install DeepStream Python Bindings
if [ -f "/opt/nvidia/deepstream/deepstream/lib/libnvdsgst_meta.so" ]; then
    echo "DeepStream installation detected."
else
    echo "Notice: DeepStream / JetPack SDK recommended for hardware-accelerated video decoding."
fi

# 5. Register Systemd Daemon Service
echo "Configuring EdgeVision systemd daemon service..."
sudo cp deploy/jetson/edgevision-pipeline.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable edgevision-pipeline.service

echo "=== Installation Completed Successfully ==="
echo "To start EdgeVision background service, run:"
echo "  sudo systemctl start edgevision-pipeline.service"
