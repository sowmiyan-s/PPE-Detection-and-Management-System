"""
Export trained YOLO model to a TensorRT FP16 engine.

⚠️  TensorRT engines are device-specific.  Run this script ON the target
    Jetson (or an identically configured machine) — not on a development PC.

Pipeline
--------
  best.pt  →  export_onnx.py  →  best.onnx
  best.onnx  →  export_tensorrt.py  →  best.engine  (FP16)
  best.engine  →  (optional) INT8 calibration  →  best_int8.engine

See docs/tensorrt_instructions.md for full build and deployment steps.

Usage
-----
python export_tensorrt.py
python export_tensorrt.py --model ppe_training/custom_model/weights/best.pt
python export_tensorrt.py --model best.pt --int8   # experimental INT8
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

import torch
_orig = torch.load
def _safe_load(f, *args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _orig(f, *args, **kwargs)
torch.load = _safe_load

from ultralytics import YOLO

log = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export YOLO model to TensorRT engine")
    parser.add_argument(
        "--model",
        default="models/best.pt",
        help="Path to trained .pt weights",
    )
    parser.add_argument("--imgsz",  type=int, default=640,  help="Input image size")
    parser.add_argument("--device", default="0",             help="GPU device index")
    parser.add_argument("--int8",       action="store_true",     help="Export INT8 engine with calibration")
    parser.add_argument("--calib_data", default="datasets/calibration", help="Directory containing calibration images for INT8")
    parser.add_argument("--batch",      type=int, default=1,     help="Batch size")
    return parser.parse_args()


def export(args: argparse.Namespace) -> str:
    if not os.path.exists(args.model):
        log.error("Model weights not found: %s", args.model)
        log.error("Train the model first: python train_model.py")
        sys.exit(1)

    precision = "INT8" if args.int8 else "FP16"
    log.info("Loading model: %s", args.model)
    log.info("Exporting to TensorRT %s engine (imgsz=%d, device=%s)", precision, args.imgsz, args.device)

    if args.int8:
        if not os.path.exists(args.calib_data):
            log.warning("Calibration directory %s not found. Creating placeholder directory...", args.calib_data)
            os.makedirs(args.calib_data, exist_ok=True)
        log.info("INT8 Calibration dataset path: %s", args.calib_data)

    log.info("This may take several minutes on first run …")

    model = YOLO(args.model)
    export_kwargs = {
        "format": "engine",
        "half": not args.int8,
        "int8": args.int8,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "device": args.device,
    }
    if args.int8 and os.path.exists(args.calib_data) and os.listdir(args.calib_data):
        export_kwargs["data"] = args.calib_data

    path = model.export(**export_kwargs)

    engine_path = path if path else args.model.replace(".pt", ".engine")

    if os.path.exists(engine_path):
        size_mb = os.path.getsize(engine_path) / 1e6
        log.info("TensorRT engine saved: %s (%.1f MB)", engine_path, size_mb)
    else:
        log.warning("Engine not found at expected path: %s", engine_path)

    return engine_path


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
    )
    args   = parse_args()
    engine = export(args)

    print(f"\nTensorRT engine: {engine}")
    print("\nTo use the engine in the server:")
    print(f"  export MODEL_PATH={engine}")
    print("  python -m src.api.server")
    print("\nSee docs/TENSORRT_GUIDE.md for calibration data, version pinning,")
    print("and DeepStream/GStreamer integration steps.")
