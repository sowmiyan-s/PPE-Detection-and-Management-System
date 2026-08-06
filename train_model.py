"""
Model training script for the EdgeVision PPE Compliance Platform.

Usage
-----
# Default (50 epochs, GPU 0)
python train_model.py

# Custom options
python train_model.py --epochs 150 --batch 16 --device cpu --imgsz 1280

Output: ppe_training/custom_model/weights/best.pt
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# PyTorch 2.6+ compatibility
import torch
_orig = torch.load
def _safe_load(f, *args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _orig(f, *args, **kwargs)
torch.load = _safe_load

from ultralytics import YOLO

log = logging.getLogger(__name__)

<<<<<<< HEAD
# Strict cuDNN configuration to prevent CUDNN_STATUS_EXECUTION_FAILED and nan loss
torch.backends.cudnn.enabled = True
torch.backends.cudnn.benchmark = False
torch.backends.cudnn.deterministic = True

def main():
    # 1. Load a pretrained model (YOLOv8 Nano is HIGHLY recommended for Jetson)
    print("Loading YOLOv8n base model...")
    model = YOLO("yolov8n.pt")  # 'n' is nano: crucial for real-time FPS on Jetson hardware
    
    # 2. Train the model
    # NOTE: Ensure you have your dataset ready and the data.yaml path is correct.
    print("Starting training process...")
    results = model.train(
        data="dataset.yaml",       # Path to your dataset's YAML configuration file
        epochs=50,              # Number of training epochs (increase to 100-300 for production accuracy)
        imgsz=640,              # Standard YOLO image size
        batch=4,                # Lowered to 4 to guarantee no Out Of Memory on 4GB VRAM
        device=0,               # Set to '0' to use your NVIDIA GPU
        amp=False,              # MUST BE FALSE FOR GTX 1650 (fixes nan loss and cuDNN crashes)
        half=False,             # Disable FP16 entirely to avoid nan losses
        optimizer="SGD",        # SGD is significantly more stable than AdamW
        lr0=0.01,               # Stable learning rate for SGD
        workers=2,              # Limit dataloader workers to prevent RAM/Pagefile crashes on Windows
        project="ppe_training", # Folder name where results will be saved
        name="custom_model"     # Name of the specific training run
=======

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train YOLOv8 PPE detection model")
    parser.add_argument("--model",   default="yolov8n.pt",       help="Base model weights")
    parser.add_argument("--data",    default="dataset.yaml",      help="Dataset config path")
    parser.add_argument("--epochs",  type=int,   default=50,      help="Training epochs (recommend 100-300 for production)")
    parser.add_argument("--imgsz",   type=int,   default=640,     help="Input image size")
    parser.add_argument("--batch",   type=int,   default=8,       help="Batch size (-1 = auto)")
    parser.add_argument("--device",  default="0",                 help="Device: 0 (GPU), cpu, mps")
    parser.add_argument("--project", default="ppe_training",      help="Output project folder")
    parser.add_argument("--name",    default="custom_model",      help="Run name")
    parser.add_argument("--resume",  action="store_true",         help="Resume from last checkpoint")
    parser.add_argument("--augment", action="store_true",
                        default=True,                             help="Enable data augmentation")
    return parser.parse_args()


def train(args: argparse.Namespace) -> str:
    # Validate dataset config
    if not os.path.exists(args.data):
        log.error("Dataset config not found: %s", args.data)
        sys.exit(1)

    # Resolve model path
    model_path = args.model
    if not os.path.exists(model_path):
        log.warning("Model not found locally (%s) – Ultralytics will download it", model_path)

    log.info("Loading base model: %s", model_path)
    model = YOLO(model_path)

    log.info(
        "Starting training: epochs=%d, imgsz=%d, batch=%d, device=%s",
        args.epochs, args.imgsz, args.batch, args.device,
>>>>>>> 23bb9ced683c99cd7b7cc1433e6c86b5f075baf1
    )

    results = model.train(
        data       = args.data,
        epochs     = args.epochs,
        imgsz      = args.imgsz,
        batch      = args.batch,
        device     = args.device,
        project    = args.project,
        name       = args.name,
        resume     = args.resume,
        # Augmentation settings for difficult environments
        augment    = args.augment,
        hsv_h      = 0.015,   # hue variation (lighting changes)
        hsv_s      = 0.7,     # saturation variation (dust, sunlight)
        hsv_v      = 0.4,     # brightness variation (low light)
        degrees    = 10.0,    # rotation (workers bending)
        flipud     = 0.1,     # vertical flip (unusual angles)
        mosaic     = 1.0,     # mosaic augmentation (crowded scenes)
        copy_paste = 0.3,     # copy-paste augmentation (occlusion)
    )

    best_weights = os.path.join(args.project, args.name, "weights", "best.pt")
    if os.path.exists(best_weights):
        log.info("Training complete. Best weights: %s", best_weights)
    else:
        log.warning("Training complete but best.pt not found at expected path: %s", best_weights)

    return best_weights


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args()
    best = train(args)
    print(f"\nBest weights saved to: {best}")
    print("Next steps:")
    print("  1. python export_onnx.py --model", best)
    print("  2. python export_tensorrt.py --model", best)
