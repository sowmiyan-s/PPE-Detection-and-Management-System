#!/usr/bin/env bash
# ==============================================================================
# EdgeVision / Cerberus AI - TensorRT FP16 Engine Compiler for Jetson Orin
# Builds hardware-accelerated TensorRT Engine directly on the target GPU
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

if [ -d "venv" ]; then
    source venv/bin/activate
fi

MODEL_PT=${1:-"models/best.pt"}
IMGSZ=${2:-640}
WORKSPACE=${3:-4}

echo "============================================================"
echo " ⚡ Compiling TensorRT FP16 Engine for NVIDIA Jetson Orin"
echo "============================================================"
echo "Source Weights: $MODEL_PT"
echo "Image Size    : $IMGSZ x $IMGSZ"
echo "Precision     : FP16 (Hardware Tensor Cores)"
echo "Workspace     : ${WORKSPACE} GB"
echo "============================================================"

if [ ! -f "$MODEL_PT" ]; then
    echo "❌ Error: PyTorch model file '$MODEL_PT' not found!"
    exit 1
fi

python3 scripts/export_tensorrt.py \
    --model "$MODEL_PT" \
    --imgsz "$IMGSZ" \
    --device 0

ENGINE_FILE="${MODEL_PT%.*}.engine"

if [ -f "$ENGINE_FILE" ]; then
    echo ""
    echo "✅ TensorRT Engine compilation succeeded: $ENGINE_FILE"
    echo "The EdgeVision runtime will automatically detect and prioritize this engine."
else
    echo "⚠️ TensorRT export completed. Engine path: $ENGINE_FILE"
fi
