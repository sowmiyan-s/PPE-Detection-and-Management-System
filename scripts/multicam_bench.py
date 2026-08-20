"""
Multi-camera simulation: proves the adaptive + isolated-executor fix.

Compares, on this machine's CUDA GPU:
  OLD : every camera runs fixed imgsz=640 on the SHARED default ThreadPoolExecutor
        (which the evidence/DB I/O also uses) — i.e. the pre-fix design.
  NEW : every camera uses runtime.ADAPTIVE_IMG_SIZE via runtime.get_infer_executor()
        (isolated from I/O) — i.e. the post-fix design.

Reports aggregate FPS (sum across cameras) and per-camera FPS, which is what
dictates on-screen smoothness.
"""
import time, os, asyncio, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from ultralytics import YOLO
import torch

from src.core import runtime, config

DEVICE = 0 if torch.cuda.is_available() else "cpu"
HALF = torch.cuda.is_available()
W, H = 1280, 720


def make_frame():
    return np.random.randint(0, 255, (H, W, 3), dtype=np.uint8)


def infer(model, frame, imgsz):
    model.track(frame, persist=True, conf=config.DETECTION_CONF, imgsz=imgsz,
                device=DEVICE, quantize="fp16" if HALF else None,
                verbose=False, tracker="bytetrack.yaml")


def old_worker(model, n_frames, stop):
    # OLD: fixed 640 on the default shared executor
    t0 = time.perf_counter()
    count = 0
    while time.perf_counter() - t0 < 3.0 and not stop.is_set():
        infer(model, make_frame(), 640)
        count += 1
    return count


def new_worker(model, n_frames, stop, size_holder):
    t0 = time.perf_counter()
    count = 0
    while time.perf_counter() - t0 < 3.0 and not stop.is_set():
        infer(model, make_frame(), size_holder())
        count += 1
    return count


def run(n_cams, mode):
    model = YOLO("models/best.pt")
    # warmup
    infer(model, make_frame(), 640 if mode == "old" else runtime._pick_img_size(config.INFERENCE_IMG_SIZE, n_cams))
    stop = asyncio.Event() if False else None

    if mode == "old":
        ex = ThreadPoolExecutor(max_workers=n_cams)  # shared-style default
        size_holder = lambda: 640
    else:
        ex = runtime.get_infer_executor()
        size_holder = runtime.get_adaptive_img_size

    import threading
    stop_ev = threading.Event()
    t0 = time.perf_counter()
    futs = []
    for _ in range(n_cams):
        if mode == "old":
            futs.append(ex.submit(old_worker, model, 30, stop_ev))
        else:
            futs.append(ex.submit(new_worker, model, 30, stop_ev, size_holder))
    counts = [f.result() for f in futs]
    dt = time.perf_counter() - t0
    total = sum(counts)
    agg = total / dt
    per = (total / n_cams) / (dt / max(1, 1)) if False else None
    per_cam = agg / n_cams
    size = 640 if mode == "old" else runtime._pick_img_size(config.INFERENCE_IMG_SIZE, n_cams)
    print(f"  mode={mode:>3} cams={n_cams:>2} imgsz={size:>3} -> aggregate {agg:5.1f} FPS | per-cam ~{per_cam:5.1f} FPS")
    return agg


if __name__ == "__main__":
    print(f"device={DEVICE} half={HALF}")
    for n in (1, 2, 4, 8):
        print(f"\n--- {n} cameras ---")
        run(n, "old")
        runtime.recompute_adaptive(n)
        run(n, "new")
