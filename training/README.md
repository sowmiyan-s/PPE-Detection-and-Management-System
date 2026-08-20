# 🎯 Cerberus AI — Model Training & Dataset Engineering

> **Repository:** [https://github.com/Vidhyasree14/Cerberus-AI](https://github.com/Vidhyasree14/Cerberus-AI) | **Developer:** Vidhyashree M

This directory contains scripts and configurations for training, validating, and fine-tuning custom YOLOv8 models for **Cerberus AI** — supporting local GPU workstations, cloud GPU platforms (Kaggle, Google Colab), and NVIDIA Jetson devices.

---

## 📂 Directory Layout

```
training/
├── train_model.py              # Main PyTorch / Ultralytics training pipeline
├── dataset.yaml                # YOLO dataset taxonomy and path configuration
├── kaggle_export/
│   ├── kaggle_training.py      # Standalone GPU training script for Kaggle (T4/P100)
│   └── kaggle_dataset.json     # Kaggle dataset mount configuration
└── colab_export/
    ├── cerberus_ai_training.ipynb  # Google Colab notebook (GPU runtime)
    └── colab_setup.sh              # Colab environment setup script
```

---

## 🏷️ PPE Detection Schema

The custom YOLO model is trained to detect compliant PPE and violation states across two functional categories:

### ✅ Compliant PPE Classes
| Class ID | Class Name | Detection Target |
| :---: | :--- | :--- |
| `0` | `Boots` | Safety footwear (steel-toed, ankle-high work boots) |
| `1` | `Ear-Protection` | Earmuffs or in-ear hearing protection plugs |
| `2` | `Glass` | Safety glasses or protective eyewear |
| `3` | `Glove` | Work gloves (leather, latex, or cut-resistant) |
| `4` | `Hard_hat` | Hard hat or construction-grade safety helmet |
| `5` | `Mask` | N95, dust mask, or full-face respirator |

### 🚨 Violation State Classes
| Class ID | Class Name | Trigger Condition |
| :---: | :--- | :--- |
| `6` | `No-Boots` | Worker without safety footwear |
| `7` | `No-Ear-Protection` | Worker without hearing protection in noisy zone |
| `8` | `No-Glass` | Worker without eye protection |
| `9` | `No-Glove` | Worker with bare hands in hazard zone |
| `10` | `No-Helmet` | Worker without head protection |
| `11` | `No-Mask` | Worker without respiratory protection |
| `12` | `No-Vest` | Worker without high-visibility vest |

---

## 🚀 Training Instructions

### Option 1: Local Workstation Training (NVIDIA GPU — Recommended)

**Prerequisites:**
- NVIDIA GPU with CUDA 12.x
- Python 3.10+
- Ultralytics 8.x installed (`pip install ultralytics`)

```bash
python training/train_model.py \
    --data data.yaml \
    --epochs 100 \
    --imgsz 640 \
    --batch 16 \
    --device 0 \
    --project runs/train \
    --name cerberus_v1
```

**Recommended Training Hyperparameters:**

| Parameter | Value | Rationale |
| :--- | :---: | :--- |
| `epochs` | 100 | Sufficient convergence for 19-class detection |
| `imgsz` | 640 | Standard YOLO input — balances accuracy vs speed |
| `batch` | 16 | For 8GB VRAM GPUs; use 32 for 16GB+ |
| `optimizer` | `AdamW` | Better convergence vs SGD for multi-class |
| `lr0` | 0.01 | Initial learning rate |
| `mosaic` | 1.0 | Enabled — critical for small PPE detection |
| `patience` | 20 | Early stopping if no improvement after 20 epochs |

---

### Option 2: Cloud GPU Training (Kaggle — Free T4/P100 GPU)

1. Mount the dataset `Construction PPE Detection Combined.yolov8` in your Kaggle notebook.
2. Upload `training/kaggle_export/kaggle_training.py` to the Kaggle notebook.
3. Enable **GPU accelerator** (T4 × 2 or P100) in notebook settings.
4. Run the training script.
5. Download the generated `runs/train/cerberus_v1/weights/best.pt` and copy it to `models/best.pt`.

```python
# kaggle_training.py — key training call
from ultralytics import YOLO

model = YOLO("yolov8n.pt")  # Start from YOLOv8 nano pretrained weights
results = model.train(
    data="/kaggle/input/ppe-dataset/data.yaml",
    epochs=100,
    imgsz=640,
    batch=32,           # Larger batch on Kaggle T4
    device=0,
    mosaic=1.0,
    project="/kaggle/working",
    name="cerberus_v1"
)
```

---

### Option 3: Google Colab Training (Free GPU Runtime)

1. Open `training/colab_export/cerberus_ai_training.ipynb` in Google Colab.
2. Set **Runtime → Change runtime type → GPU (T4)**.
3. Mount Google Drive for persistent checkpoint storage.
4. Run all cells sequentially.
5. Download `best.pt` from the Drive output path.

---

## 📂 Placing Trained Weights

After training is complete, place the output weights into the `models/` directory:

```bash
# From local training
cp runs/train/cerberus_v1/weights/best.pt models/best.pt

# From Kaggle/Colab download
mv ~/Downloads/best.pt models/best.pt
```

Then (optionally) compile TensorRT engine for 2–3× faster inference:
```bash
python scripts/export_tensorrt.py --model models/best.pt --imgsz 640 --half --device 0
```

See [TensorRT Acceleration Guide](../docs/TENSORRT_GUIDE.md) for details.

---

## 📈 Evaluating Your Trained Model

```bash
# Validate on the test split
python -c "
from ultralytics import YOLO
model = YOLO('models/best.pt')
results = model.val(data='data.yaml', split='test', imgsz=640)
print(f'mAP@50: {results.box.map50:.3f}')
print(f'mAP@50-95: {results.box.map:.3f}')
"
```

**Target metrics for production deployment:**
- `mAP@50` ≥ 85% overall
- `Hard_hat` mAP@50 ≥ 90%
- `Worker` mAP@50 ≥ 95%

---

## 🔄 Fine-Tuning on Site-Specific Data

To improve accuracy for a specific industrial site or lighting environment:

```bash
# Fine-tune from existing Cerberus AI weights
python training/train_model.py \
    --model models/best.pt \        # Start from pre-trained weights (not yolov8n.pt)
    --data data.yaml \
    --epochs 30 \                   # Fewer epochs for fine-tuning
    --lr0 0.001 \                   # Lower learning rate for fine-tuning
    --batch 8 \
    --device 0
```

---

*Part of the [Cerberus AI](https://github.com/Vidhyasree14/Cerberus-AI) platform — developed by Vidhyashree M.*