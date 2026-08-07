"""
EdgeVision ONNX Model Exporter
Converts trained PyTorch YOLOv8 weights (.pt) to ONNX format.

Usage:
  python scripts/export_onnx.py --model experiments/ppe_training/custom_model/weights/best.pt
"""

import argparse
import os
import sys
from ultralytics import YOLO

def main():
    parser = argparse.ArgumentParser(description="Export PyTorch YOLOv8 model to ONNX format.")
    parser.add_argument(
        "--model",
        type=str,
        default="experiments/ppe_training/custom_model/weights/best.pt",
        help="Path to trained PyTorch weights (.pt)"
    )
    parser.add_argument("--imgsz", type=int, default=640, help="Inference resolution size")
    args = parser.parse_args()

    if not os.path.exists(args.model):
        print(f"Error: Model file {args.model} not found.")
        sys.exit(1)

    print(f"Loading PyTorch model from: {args.model}")
    model = YOLO(args.model)

    print("Exporting model to ONNX format...")
    onnx_path = model.export(format="onnx", imgsz=args.imgsz, dynamic=True)
    print(f"Successfully exported ONNX model to: {onnx_path}")

if __name__ == "__main__":
    main()
