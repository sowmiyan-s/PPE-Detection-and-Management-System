import os
import torch
from ultralytics import YOLO

# ============================================================
# 1. CHECK GPU
# ============================================================

print("=" * 60)
print("SYSTEM INFORMATION")
print("=" * 60)

print(f"PyTorch Version : {torch.__version__}")
print(f"CUDA Available  : {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"GPU             : {torch.cuda.get_device_name(0)}")
    print(f"CUDA Version    : {torch.version.cuda}")
else:
    print("WARNING: CUDA GPU not detected. Training will use CPU.")

# ============================================================
# 2. DATASET PATH
# ============================================================

# Dataset folder is located beside this Python file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE_DIR, "Dataset")

# data.yaml inside Dataset folder
yaml_path = os.path.join(DATASET_DIR, "data.yaml")

if not os.path.exists(yaml_path):
    raise FileNotFoundError(
        f"\ndata.yaml not found!\nExpected location:\n{yaml_path}"
    )

print("\n" + "=" * 60)
print("DATASET INFORMATION")
print("=" * 60)

print(f"Dataset folder : {DATASET_DIR}")
print(f"YAML file      : {yaml_path}")

# ============================================================
# 3. LOAD DATASET CONFIGURATION
# ============================================================

import yaml

with open(yaml_path, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

print(f"Classes        : {config.get('names')}")
print(f"Number classes : {config.get('nc')}")

# ============================================================
# 4. LOAD YOLO11 NANO MODEL
# ============================================================

print("\n" + "=" * 60)
print("LOADING YOLO MODEL")
print("=" * 60)

model = YOLO("yolo11n.pt")

# ============================================================
# 5. TRAIN
# ============================================================

print("\n" + "=" * 60)
print("STARTING TRAINING")
print("=" * 60)

device = 0 if torch.cuda.is_available() else "cpu"

results = model.train(
    data=yaml_path,

    # Training
    epochs=50,
    imgsz=640,
    batch=16,

    # GPU / CPU
    device=device,

    # Output
    project=os.path.join(BASE_DIR, "runs"),
    name="ppe_yolo11",
    exist_ok=True,

    # Recommended settings
    pretrained=True,
    workers=4,

    # Save checkpoints
    save=True,
    save_period=10,

    # Validation
    val=True,

    # Cache images for faster training if RAM allows
    cache=False
)

# ============================================================
# 6. TRAINING COMPLETE
# ============================================================

print("\n" + "=" * 60)
print("TRAINING COMPLETED")
print("=" * 60)

print(f"Results saved to:")
print(os.path.join(BASE_DIR, "runs", "ppe_yolo11"))

print("\nBest model:")
print(os.path.join(BASE_DIR, "runs", "ppe_yolo11", "weights", "best.pt"))

print("\nLast model:")
print(os.path.join(BASE_DIR, "runs", "ppe_yolo11", "weights", "last.pt"))