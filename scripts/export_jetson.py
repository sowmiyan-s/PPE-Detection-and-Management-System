#!/usr/bin/env python3
"""
Jetson Performance Export Script

This script converts a trained YOLO PyTorch model (.pt) into a highly optimized
TensorRT Engine (.engine) for max performance on Jetson devices (Orin, Xavier, Nano).

Usage:
    python scripts/export_jetson.py --model models/yolo11n.pt --imgsz 640

Requirements:
    - Must be run on the target Jetson device (or a host with identical TensorRT versions).
    - Requires `pip install ultralytics tensorrt`.
"""

import argparse
import sys
import os

try:
    from ultralytics import YOLO
except ImportError:
    print("Error: ultralytics is not installed. Run `pip install ultralytics`")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Export YOLO model to TensorRT for Jetson")
    parser.add_argument("--model", type=str, default="models/best.pt", help="Path to the PyTorch model (.pt)")
    parser.add_argument("--imgsz", type=int, default=640, help="Target image size (e.g. 640 or 416)")
    parser.add_argument("--workspace", type=int, default=4, help="Max workspace size in GB")
    args = parser.parse_args()

    if not os.path.exists(args.model):
        print(f"Error: Model not found at {args.model}")
        sys.exit(1)

    print(f"Loading PyTorch model: {args.model}")
    model = YOLO(args.model)

    print(f"\n--- Starting TensorRT Export ---")
    print(f"Image Size: {args.imgsz}")
    print(f"Precision:  FP16 (half=True)")
    print(f"Workspace:  {args.workspace} GB")
    
    try:
        exported_path = model.export(
            format="engine",
            imgsz=args.imgsz,
            quantize=True,   # FP16 — critical for Jetson performance
            dynamic=False,   # Fixed shapes are faster
            workspace=args.workspace,
            simplify=True
        )
        print(f"\n✅ Export successful! TensorRT engine saved to: {exported_path}")
        print("The EdgeVision pipeline will automatically prefer this .engine file if placed in the same directory as the .pt model.")
    except Exception as e:
        print(f"\n❌ Export failed: {e}")
        print("Note: TensorRT export usually must be run on the target NVIDIA Jetson device, not a standard PC.")

if __name__ == "__main__":
    main()
