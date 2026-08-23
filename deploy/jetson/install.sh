#!/usr/bin/env bash
# ==============================================================================
# EdgeVision / Cerberus AI - NVIDIA Jetson Orin Automated Setup & Provisioning
# Target Platform: NVIDIA Jetson Orin Nano / Orin NX / AGX Orin
# OS: Ubuntu 20.04 / 22.04 LTS (JetPack 5.1 / 6.0+)
# Architecture: aarch64 (ARM64)
# ==============================================================================

set -e

# Terminal Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}   🚀 EdgeVision NVIDIA Jetson Orin Automated Setup        ${NC}"
echo -e "${CYAN}============================================================${NC}"

# 1. Hardware & Platform Verification
echo -e "\n${BLUE}[1/7] Detecting Jetson Hardware & OS Environment...${NC}"
ARCH=$(uname -m)
if [ "$ARCH" != "aarch64" ]; then
    echo -e "${YELLOW}⚠️  Notice: System architecture is '$ARCH' (expected aarch64 for Jetson).${NC}"
    echo -e "${YELLOW}   Continuing installation in generic Linux mode...${NC}"
else
    echo -e "${GREEN}✓ Architecture: $ARCH (ARM64)${NC}"
fi

if [ -f "/proc/device-tree/model" ]; then
    JETSON_MODEL=$(tr -d '\0' < /proc/device-tree/model)
    echo -e "${GREEN}✓ Detected Hardware: ${JETSON_MODEL}${NC}"
elif [ -f "/etc/nv_tegra_release" ]; then
    TEGRA_INFO=$(head -n 1 /etc/nv_tegra_release)
    echo -e "${GREEN}✓ Detected Tegra Release: ${TEGRA_INFO}${NC}"
fi

# 2. Update APT Package Repositories
echo -e "\n${BLUE}[2/7] Updating APT package repositories and installing system dependencies...${NC}"
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
    python3-pip \
    python3-dev \
    python3-venv \
    build-essential \
    pkg-config \
    cmake \
    libopencv-dev \
    ffmpeg \
    v4l-utils \
    git \
    curl \
    libgirepository1.0-dev \
    libcairo2-dev \
    python3-gi \
    gir1.2-gstreamer-1.0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-tools

echo -e "${GREEN}✓ System packages installed successfully.${NC}"

# 3. Optimize Jetson Power Mode & Clocks
echo -e "\n${BLUE}[3/7] Setting Jetson Orin to Maximum Performance Mode (MAXN)...${NC}"
if command -v nvpmodel &> /dev/null; then
    sudo nvpmodel -m 0 || true
    echo -e "${GREEN}✓ Power Mode set to MAXN (Mode 0).${NC}"
fi

if command -v jetson_clocks &> /dev/null; then
    sudo jetson_clocks || true
    echo -e "${GREEN}✓ Jetson Clocks locked to maximum frequency.${NC}"
fi

# 4. Install Jetson Performance Monitoring Tool (jtop)
echo -e "\n${BLUE}[4/7] Ensuring 'jetson-stats' (jtop) telemetry utility is installed...${NC}"
sudo pip3 install -U jetson-stats || true

# 5. Setup Python Environment
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

echo -e "\n${BLUE}[5/7] Configuring Python virtual environment with system site-packages...${NC}"
# Use --system-site-packages to inherit JetPack TensorRT, PyTorch, and GStreamer bindings
if [ ! -d "venv" ]; then
    python3 -m venv --system-site-packages venv
    echo -e "${GREEN}✓ Created Python virtual environment 'venv' with system site packages.${NC}"
fi

source venv/bin/activate
pip install --upgrade pip setuptools wheel

echo -e "\n${BLUE}[6/7] Installing Python requirements for Jetson Orin...${NC}"
if [ -f "deploy/jetson/requirements-jetson.txt" ]; then
    pip install -r deploy/jetson/requirements-jetson.txt
else
    pip install -r requirements.txt
fi

# 6. Make Deployment & Evaluation Scripts Executable
echo -e "\n${BLUE}[7/7] Configuring execution permissions and sample test assets...${NC}"
chmod +x deploy/jetson/*.sh || true

# Generate sample demo test video if not already present
if [ ! -f "database/evidence/sample_demo.mp4" ]; then
    echo "Generating offline sample test video for instant camera-less verification..."
    python3 scripts/generate_sample_video.py || true
fi

echo -e "\n${GREEN}============================================================${NC}"
echo -e "${GREEN}   ✅ Jetson Orin Deployment Setup Completed Successfully!  ${NC}"
echo -e "${GREEN}============================================================${NC}"
echo -e "\nNext Steps for Evaluation & Demonstration:"
echo -e "  1. Compile TensorRT FP16 Engine (first-time on Jetson):"
echo -e "     ${CYAN}./deploy/jetson/export_engine.sh${NC}"
echo -e "  2. Run the Full Application Server (Web UI & Stream Hub):"
echo -e "     ${CYAN}./deploy/jetson/start.sh${NC}"
echo -e "  3. Or run instant camera / video demo:"
echo -e "     ${CYAN}./deploy/jetson/run_demo.sh --source 0${NC}          (USB Webcam)"
echo -e "     ${CYAN}./deploy/jetson/run_demo.sh --source csi://0${NC}    (CSI Camera)"
echo -e "     ${CYAN}./deploy/jetson/run_demo.sh --source sample${NC}     (Sample Video)"
echo -e "  4. Run Performance & FPS Latency Benchmark:"
echo -e "     ${CYAN}./deploy/jetson/run_benchmark.sh${NC}"
echo -e "============================================================\n"
