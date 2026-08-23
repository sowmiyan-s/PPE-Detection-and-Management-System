#!/usr/bin/env bash
# ==============================================================================
# EdgeVision / Cerberus AI - NVIDIA Jetson Orin Hardware Benchmark
# Measures real-time latency, throughput (FPS), GPU VRAM, and thermal metrics
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

if [ -d "venv" ]; then
    source venv/bin/activate
fi

MODEL=${1:-"models/best.engine"}
if [ ! -f "$MODEL" ]; then
    MODEL="models/best.pt"
fi

ITERS=${2:-100}
IMGSZ=${3:-640}

echo "============================================================"
echo " ⚡ NVIDIA Jetson Orin Edge Performance Benchmark"
echo " Model      : $MODEL"
echo " Iterations : $ITERS"
echo " Image Size : $IMGSZ x $IMGSZ"
echo "============================================================"

python3 -c "
import time, os, sys
import numpy as np
import psutil

try:
    import torch
    has_cuda = torch.cuda.is_available()
    device_name = torch.cuda.get_device_name(0) if has_cuda else 'CPU'
except Exception:
    has_cuda = False
    device_name = 'CPU'

from ultralytics import YOLO

model_path = '$MODEL'
iters = int('$ITERS')
imgsz = int('$IMGSZ')

print(f'[INFO] Platform: {device_name} (CUDA={has_cuda})')
print(f'[INFO] Loading model: {model_path} ...')
t0 = time.time()
model = YOLO(model_path)
load_time = (time.time() - t0) * 1000.0
print(f'✓ Model loaded in {load_time:.1f} ms')

# Generate synthetic frame (1280x720 RGB)
frame = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)

# Warmup run (5 iterations)
print('[INFO] Executing GPU warmup runs...')
for _ in range(5):
    _ = model.predict(frame, imgsz=imgsz, half=has_cuda, verbose=False)

print(f'[INFO] Running {iters} benchmark iterations...')
latencies = []
t_total_start = time.perf_counter()

for _ in range(iters):
    t_start = time.perf_counter()
    _ = model.predict(frame, imgsz=imgsz, half=has_cuda, verbose=False)
    t_end = time.perf_counter()
    latencies.append((t_end - t_start) * 1000.0)

t_total_end = time.perf_counter()
total_time = t_total_end - t_total_start
avg_fps = iters / total_time

latencies.sort()
p50 = latencies[int(0.50 * len(latencies))]
p95 = latencies[int(0.95 * len(latencies))]
p99 = latencies[int(0.99 * len(latencies))]
avg_lat = sum(latencies) / len(latencies)

ram = psutil.virtual_memory()
cpu = psutil.cpu_percent(interval=0.1)

# Check Jetson SoC temperature if available
temp_str = 'N/A'
temp_file = '/sys/devices/virtual/thermal/thermal_zone0/temp'
if os.path.exists(temp_file):
    try:
        with open(temp_file, 'r') as f:
            temp_c = float(f.read().strip()) / 1000.0
            temp_str = f'{temp_c:.1f}°C'
    except Exception:
        pass

print('\n' + '=' * 60)
print('             📊 JETSON ORIN BENCHMARK RESULTS')
print('=' * 60)
print(f' Hardware Device        : {device_name}')
print(f' SoC Temperature        : {temp_str}')
print(f' CPU Utilization        : {cpu}%')
print(f' RAM Memory Used        : {ram.used / (1024**3):.2f} GB / {ram.total / (1024**3):.2f} GB ({ram.percent}%)')
if has_cuda:
    vram_alloc = torch.cuda.memory_allocated(0) / (1024**2)
    vram_res = torch.cuda.memory_reserved(0) / (1024**2)
    print(f' GPU VRAM Allocated     : {vram_alloc:.1f} MB (Reserved: {vram_res:.1f} MB)')
print('-' * 60)
print(f' Average Inference Time : {avg_lat:.2f} ms')
print(f' P50 (Median) Latency   : {p50:.2f} ms')
print(f' P95 Inference Latency  : {p95:.2f} ms')
print(f' P99 Inference Latency  : {p99:.2f} ms')
print(f' Aggregate Throughput   : {avg_fps:.1f} FPS')
print('-' * 60)
if avg_fps >= 30:
    print(' Status: 🟢 EXCELLENT - Exceeds 30 FPS Real-Time Baseline')
elif avg_fps >= 15:
    print(' Status: 🟡 OPTIMAL - Meets Industrial 15-20 FPS Requirement')
else:
    print(' Status: 🔴 LOW - Recommendation: Enable TensorRT FP16 Export')
print('=' * 60 + '\n')
"
