#!/usr/bin/env bash
# ==============================================================================
# EdgeVision / Cerberus AI - Start Server on NVIDIA Jetson Orin
# Starts FastAPI Live Inference Engine, WebSocket Streamer, and Telemetry Hub
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Export Jetson-optimized environment variables
export PERFORMANCE_PROFILE="jetson"
export SERVER_HOST="0.0.0.0"
export PORT=${PORT:-8000}
export INFERENCE_HALF_PRECISION="true"
export CUDA_VISIBLE_DEVICES=0
export PYTHONUNBUFFERED=1

# If TensorRT engine exists, use it
if [ -f "models/best.engine" ]; then
    export MODEL_PATH="models/best.engine"
    echo "⚡ Using hardware-accelerated TensorRT engine: models/best.engine"
elif [ -f "models/best.pt" ]; then
    export MODEL_PATH="models/best.pt"
    echo "ℹ️ Using PyTorch weights: models/best.pt"
fi

echo "============================================================"
echo " 🚀 Starting EdgeVision on NVIDIA Jetson Orin"
echo " Host: http://${SERVER_HOST}:${PORT}"
echo " WebSocket Stream: ws://${SERVER_HOST}:${PORT}/ws"
echo " MJPEG Feed: http://${SERVER_HOST}:${PORT}/api/stream"
echo " Metrics API: http://${SERVER_HOST}:${PORT}/api/device/metrics"
echo "============================================================"

exec python3 -m src.api.server
