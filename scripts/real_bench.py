"""
Real inference benchmark for EdgeVision PPE detector.
Measures actual YOLO track FPS on GPU with the project's custom model so we
can quantify the impact of optimizations (batch, imgsz, half, onnx).
"""
import time, sys, os
import numpy as np
import cv2

import torch
_is_gpu = torch.cuda.is_available()
print(f"torch {torch.__version__}  cuda_available={_is_gpu}  device={'cuda:0' if _is_gpu else 'cpu'}")

from ultralytics import YOLO

MODEL = "models/best.pt"
DEVICE = 0 if _is_gpu else "cpu"
HALF = _is_gpu  # fp16 only valid on GPU

# synthetic frame sized like a real camera feed
W, H = 1280, 720
frame = np.random.randint(0, 255, (H, W, 3), dtype=np.uint8)

def make_frames(n):
    return [np.random.randint(0, 255, (H, W, 3), dtype=np.uint8) for _ in range(n)]

def bench_track(model, imgsz, batch=1, iters=30):
    # warmup
    if batch == 1:
        model.track(frame, persist=True, conf=0.35, imgsz=imgsz, device=DEVICE,
                    half=HALF, verbose=False, tracker="bytetrack.yaml")
    t0 = time.perf_counter()
    for _ in range(iters):
        if batch == 1:
            model.track(frame, persist=True, conf=0.35, imgsz=imgsz, device=DEVICE,
                        half=HALF, verbose=False, tracker="bytetrack.yaml")
        else:
            frames = make_frames(batch)
            model.track(frames, persist=True, conf=0.35, imgsz=imgsz, device=DEVICE,
                        half=HALF, verbose=False, tracker="bytetrack.yaml")
    dt = time.perf_counter() - t0
    fps = (iters * (1 if batch == 1 else batch)) / dt
    print(f"  track imgsz={imgsz} batch={batch} half={HALF}: {fps:5.1f} FPS ({(dt/iters)*1000:.1f} ms/call)")
    return fps

print("\n=== Loading custom model %s ===" % MODEL)
t0 = time.perf_counter()
model = YOLO(MODEL)
print(f"  load took {time.perf_counter()-t0:.1f}s  classes={list(model.names.values())}")

print("\n=== Single-frame track FPS ===")
bench_track(model, 640)
bench_track(model, 480)
bench_track(model, 320)

print("\n=== Batched track FPS (multi-camera simulation, GPU) ===")
if _is_gpu:
    for b in (2, 4, 6, 8):
        bench_track(model, 640, batch=b)
else:
    print("  (skipped: CPU)")

print("\nDone.")
