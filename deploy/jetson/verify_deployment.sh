#!/usr/bin/env bash
# ==============================================================================
# EdgeVision / Cerberus AI - Jetson On-Device Deployment Verification
# Run this AFTER install.sh to verify everything is correctly configured
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS=0
FAIL=0

check_pass() {
    echo -e "  ${GREEN}✅ PASS${NC}  $1"
    ((PASS++))
}

check_fail() {
    echo -e "  ${RED}❌ FAIL${NC}  $1  ($2)"
    ((FAIL++))
}

echo -e "${CYAN}============================================================${NC}"
echo -e "${CYAN}  🔍 EdgeVision Jetson On-Device Verification${NC}"
echo -e "${CYAN}============================================================${NC}"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

# 1. Architecture
echo -e "\n${CYAN}[1/9] System Architecture${NC}"
ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ]; then
    check_pass "Architecture: $ARCH (ARM64 Jetson)"
else
    check_fail "Architecture: $ARCH" "Expected aarch64 for Jetson"
fi

# 2. Jetson Hardware Detection
echo -e "\n${CYAN}[2/9] Jetson Hardware Detection${NC}"
if [ -f "/proc/device-tree/model" ]; then
    MODEL=$(tr -d '\0' < /proc/device-tree/model)
    check_pass "Jetson Model: $MODEL"
elif [ -f "/etc/nv_tegra_release" ]; then
    check_pass "Tegra Release: $(head -n1 /etc/nv_tegra_release)"
else
    check_fail "Jetson hardware" "Not detected — are you on a Jetson device?"
fi

# 3. CUDA & TensorRT
echo -e "\n${CYAN}[3/9] CUDA & TensorRT${NC}"
if command -v nvcc &> /dev/null; then
    CUDA_VER=$(nvcc --version | grep "release" | sed 's/.*release //' | sed 's/,.*//')
    check_pass "CUDA: $CUDA_VER"
else
    check_fail "CUDA (nvcc)" "Not found in PATH"
fi

if dpkg -l 2>/dev/null | grep -q "tensorrt"; then
    TRT_VER=$(dpkg -l | grep "libnvinfer[0-9]" | head -1 | awk '{print $3}')
    check_pass "TensorRT: $TRT_VER"
elif pip3 show tensorrt &>/dev/null; then
    check_pass "TensorRT (pip): installed"
else
    check_fail "TensorRT" "Not installed — run: sudo apt install tensorrt"
fi

# 4. Python Environment
echo -e "\n${CYAN}[4/9] Python Environment${NC}"
if [ -d "venv" ]; then
    check_pass "Virtual environment (venv/) exists"
    source venv/bin/activate
else
    check_fail "Virtual environment" "Run: python3 -m venv --system-site-packages venv"
fi

python3 -c "import ultralytics; print(ultralytics.__version__)" &>/dev/null && \
    check_pass "ultralytics: $(python3 -c 'import ultralytics; print(ultralytics.__version__)')" || \
    check_fail "ultralytics" "pip install ultralytics"

python3 -c "import cv2; print(cv2.__version__)" &>/dev/null && \
    check_pass "OpenCV: $(python3 -c 'import cv2; print(cv2.__version__)')" || \
    check_fail "OpenCV" "pip install opencv-python-headless"

python3 -c "import torch; print(f'PyTorch {torch.__version__}, CUDA={torch.cuda.is_available()}')" &>/dev/null && \
    check_pass "PyTorch: $(python3 -c 'import torch; print(f"{torch.__version__} CUDA={torch.cuda.is_available()}")')" || \
    check_fail "PyTorch" "Install from NVIDIA JetPack PyTorch wheel"

python3 -c "import psutil" &>/dev/null && \
    check_pass "psutil: installed" || \
    check_fail "psutil" "pip install psutil"

python3 -c "import fastapi" &>/dev/null && \
    check_pass "FastAPI: installed" || \
    check_fail "FastAPI" "pip install fastapi"

# 5. Model Files
echo -e "\n${CYAN}[5/9] Model Files${NC}"
if [ -f "models/best.pt" ]; then
    SIZE=$(du -h models/best.pt | cut -f1)
    check_pass "PyTorch weights: models/best.pt ($SIZE)"
else
    check_fail "models/best.pt" "MISSING — copy your trained weights here"
fi

if [ -f "models/best.engine" ]; then
    SIZE=$(du -h models/best.engine | cut -f1)
    check_pass "TensorRT engine: models/best.engine ($SIZE)"
else
    echo -e "  ${YELLOW}⚠️  INFO${NC}  models/best.engine not found — run: ./deploy/jetson/export_engine.sh"
fi

# 6. Label Consistency
echo -e "\n${CYAN}[6/9] Label & Class Consistency${NC}"
if [ -f "data.yaml" ] && [ -f "deploy/jetson/labels.txt" ]; then
    NC_YAML=$(python3 -c "import yaml; print(yaml.safe_load(open('data.yaml'))['nc'])" 2>/dev/null || echo "0")
    NC_LABELS=$(wc -l < deploy/jetson/labels.txt | tr -d ' ')
    if [ "$NC_YAML" = "$NC_LABELS" ]; then
        check_pass "data.yaml nc=$NC_YAML matches labels.txt ($NC_LABELS lines)"
    else
        check_fail "Class count mismatch" "data.yaml nc=$NC_YAML but labels.txt has $NC_LABELS lines"
    fi
else
    check_fail "data.yaml or labels.txt" "File missing"
fi

# 7. Camera Access
echo -e "\n${CYAN}[7/9] Camera Access${NC}"
if [ -e "/dev/video0" ]; then
    check_pass "USB Camera: /dev/video0 available"
else
    echo -e "  ${YELLOW}⚠️  INFO${NC}  /dev/video0 not found — plug in a USB camera or use RTSP source"
fi

if command -v nvarguscamerasrc &>/dev/null || [ -e "/dev/video0" ]; then
    check_pass "Video input available"
fi

# 8. Environment File
echo -e "\n${CYAN}[8/9] Environment Configuration${NC}"
if [ -f ".env" ]; then
    check_pass ".env file exists"
    PROFILE=$(grep "PERFORMANCE_PROFILE" .env 2>/dev/null | cut -d'=' -f2 || echo "not set")
    if [ "$PROFILE" = "jetson" ]; then
        check_pass "PERFORMANCE_PROFILE=jetson"
    else
        check_fail "PERFORMANCE_PROFILE" "Should be 'jetson', got '$PROFILE'"
    fi
else
    check_fail ".env file" "Run: cp .env.jetson.example .env"
fi

# 9. EdgeVision Core Import Test
echo -e "\n${CYAN}[9/9] Full Pipeline Import Test${NC}"
if python3 -c "
from src.core.vision_pipeline import VisionPipeline
from src.core import config, db, sqlite_db, runtime
from src.core.device_telemetry import get_full_device_performance_summary
from src.api.server import app
print('OK')
" 2>/dev/null | grep -q "OK"; then
    check_pass "All EdgeVision modules import successfully"
else
    check_fail "Module import" "Run: python3 -c 'from src.api.server import app' to see errors"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
TOTAL=$((PASS + FAIL))
echo -e "\n${CYAN}============================================================${NC}"
if [ "$FAIL" -eq 0 ]; then
    echo -e "  ${GREEN}🎉 ALL $TOTAL CHECKS PASSED — READY TO DEPLOY!${NC}"
    echo -e "\n  Next Steps:"
    echo -e "    1. Compile TensorRT engine: ${CYAN}./deploy/jetson/export_engine.sh${NC}"
    echo -e "    2. Start the server:        ${CYAN}./deploy/jetson/start.sh${NC}"
    echo -e "    3. Open dashboard:          ${CYAN}http://$(hostname -I | awk '{print $1}'):8000${NC}"
else
    echo -e "  ${RED}⚠️  $FAIL/$TOTAL CHECKS FAILED — Fix the issues above before running${NC}"
fi
echo -e "${CYAN}============================================================${NC}\n"

exit $FAIL
