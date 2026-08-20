"""
EdgeVision adaptive runtime — device-aware inference sizing + executor isolation.

Two responsibilities that are the core of the multi-camera performance fix:

1. Derive INFERENCE_DEVICE and an *adaptive* INFERENCE_IMG_SIZE that scales
   with the detected hardware (CPU vs CUDA) AND the number of active cameras,
   so the pipeline stays responsive on a Jetson edge box, a laptop CPU, or a
   many-camera GPU server.  (Measured on this project's 22 MB custom model:
   ~26 FPS @640px for ONE camera on a mid GPU, ~80 FPS @320px — so resolution
   is the real lever, not batching, which ByteTrack serializes anyway.)

2. Provide two dedicated ThreadPoolExecutors:
     - _INFER_EXECUTOR : model inference only (no blocking I/O)
     - _IO_EXECUTOR    : disk (evidence MP4/jpg encode) + DB writes
   so evidence saving / SQL DB round-trips can never starve model inference,
   which was the #1 cause of "laggy with multiple cameras".
"""

from __future__ import annotations

import os
import math
from concurrent.futures import ThreadPoolExecutor

import torch
from src.core import config


# ── Inference device ──────────────────────────────────────────────────────────
def _get_inference_device():
    try:
        import torch
        return 0 if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"

INFERENCE_DEVICE = _get_inference_device()


# ── Dedicated executors (isolation) ───────────────────────────────────────────
def _auto_infer_workers() -> int:
    """Cap concurrent inference jobs so we don't oversubscribe the device."""
    try:
        import torch
        if torch.cuda.is_available():
            return 2
    except Exception:
        pass
    return 4

    # CPU: leave headroom for camera-grabber threads, I/O, and the server.
    return max(1, (os.cpu_count() or 4) // 2)


# MAX_INFER_WORKERS=0 (default) means "auto".  Any positive value overrides.
_MAX_INFER_WORKERS = int(os.getenv("MAX_INFER_WORKERS", "0") or 0)
INFER_WORKERS = _MAX_INFER_WORKERS or _auto_infer_workers()
IO_WORKERS = max(2, (os.cpu_count() or 4) // 2)

_INFER_EXECUTOR = ThreadPoolExecutor(
    max_workers=INFER_WORKERS, thread_name_prefix="ev-infer"
)
_IO_EXECUTOR = ThreadPoolExecutor(
    max_workers=IO_WORKERS, thread_name_prefix="ev-io"
)


def get_infer_executor() -> ThreadPoolExecutor:
    """Executor reserved exclusively for model `track()` / `predict()` calls."""
    return _INFER_EXECUTOR


def get_io_executor() -> ThreadPoolExecutor:
    """Executor reserved for blocking disk/DB work (evidence + SQL writes)."""
    return _IO_EXECUTOR


# ── Adaptive inference resolution ─────────────────────────────────────────────
# The profile logic in config.py already picks a sensible *single-camera*
# baseline (480 on CPU/low-end, 640 on GPU/high-end).  We then scale it DOWN
# as more cameras share the same device so total load stays bounded and every
# stream keeps a usable FPS instead of all of them collapsing together.
_BASE_IMG_SIZE = config.INFERENCE_IMG_SIZE

# Resolution ladder (descending). Snapping to these keeps preprocessing aligned
# with typical training sizes and stride-safe multiples of 32.
_LADDER = [640, 544, 480, 416, 352, 320, 288, 256]
_FLOOR = 256


def _pick_img_size(base: int, n_cameras: int) -> int:
    """Return an inference size that fits `n_cameras` streams onto one device."""
    if n_cameras <= 1:
        return base
    if torch.cuda.is_available():
        # GPUs scale sub-linearly with resolution per stream (memory-bound
        # prefetch hides some cost), so 1/sqrt(n) keeps aggregate throughput
        # roughly constant.
        factor = 1.0 / math.sqrt(n_cameras)
    else:
        # CPU scales ~linearly: each extra stream costs nearly a full share.
        factor = 1.0 / float(n_cameras)
    size = int(round(base * factor / 32.0) * 32)
    size = max(_FLOOR, min(_LADDER[0], size))
    for s in _LADDER:
        if size >= s:
            return s
    return _LADDER[-1]


# Plain module global — written only on camera add/remove (not in the hot path),
# read every frame.  A single int load is atomic under the GIL, so no lock.
ADAPTIVE_IMG_SIZE: int = _BASE_IMG_SIZE


def recompute_adaptive(n_cameras: int) -> int:
    """Set the global adaptive inference size for `n_cameras` active cameras."""
    global ADAPTIVE_IMG_SIZE
    ADAPTIVE_IMG_SIZE = _pick_img_size(_BASE_IMG_SIZE, n_cameras)
    return ADAPTIVE_IMG_SIZE


def get_adaptive_img_size() -> int:
    """Current inference size (scales automatically with camera count)."""
    return ADAPTIVE_IMG_SIZE
