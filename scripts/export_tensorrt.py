"""
EdgeVision TensorRT FP16/INT8 Engine Exporter
Converts PyTorch (.pt) or ONNX (.onnx) models to TensorRT (.engine) format for Jetson hardware.

Usage:
  python scripts/export_tensorrt.py --model experiments/ppe_training/custom_model/weights/best.pt --half
"""

import argparse
import os
import sys
from ultralytics import YOLO

def main():
    parser = argparse.ArgumentParser(description="Export YOLOv8 model to TensorRT FP16/INT8 engine.")
    parser.add_argument(
        "--model",
        type=str,
        default="experiments/ppe_training/custom_model/weights/best.pt",
        help="Path to input weights (.pt or .onnx)"
    )
    parser.add_argument("--imgsz", type=int, default=640, help="Inference resolution size")
    parser.add_argument("--half", action="store_true", default=True, help="Use FP16 precision mode")
    parser.add_argument("--int8", action="store_true", default=False, help="Use INT8 precision mode")
    args = parser.parse_args()

    if not os.path.exists(args.model):
        print(f"Error: Model file {args.model} not found.")
        sys.exit(1)

    print(f"Loading model from: {args.model}")
    model = YOLO(args.model)

    print(f"Exporting to TensorRT .engine (FP16={args.half}, INT8={args.int8})...")
    try:
        engine_path = model.export(
            format="engine",
            imgsz=args.imgsz,
            half=args.half,
            int8=args.int8,
            device=0
        )
        print(f"Successfully generated TensorRT engine: {engine_path}")
    except Exception as e:
        print(f"TensorRT export error: {e}")
        print("Note: Ensure 'tensorrt' python package and CUDA/cuDNN are installed on your NVIDIA Jetson / GPU environment.")

if __name__ == "__main__":
    main()
