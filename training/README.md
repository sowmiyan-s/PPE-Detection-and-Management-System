# 🎯 Cerberus AI — Model Training & Dataset Engineering

This directory contains scripts and configurations for training, validating, and fine-tuning custom YOLO models for **Cerberus AI**.

---

## 📂 Directory Layout

```
training/
├── train_model.py          # PyTorch / Ultralytics model training pipeline
├── dataset.yaml            # 19-class YOLO dataset taxonomy definition
├── kaggle_export/          # Standalone training script for Kaggle GPU execution
└── colab_export/           # Google Colab notebook and configuration
```

---

## 🏷️ 19-Class Industrial Schema

The custom YOLO model is trained to recognize 19 distinct industrial object and violation classes:

| Class ID | Class Name | Category | Class ID | Class Name | Category |
| :---: | :--- | :--- | :---: | :--- | :--- |
| `0` | `Boots` | Compliant PPE | `10` | `No-Helmet` | Violation State |
| `1` | `Ear-Protection` | Compliant PPE | `11` | `No-Mask` | Violation State |
| `2` | `Glass` | Compliant PPE | `12` | `No-Vest` | Violation State |
| `3` | `Glove` | Compliant PPE | `13` | `Worker` | Core Subject |
| `4` | `Hard_hat` | Compliant PPE | `14` | `Vest` | Compliant PPE |
| `5` | `Mask` | Compliant PPE | `15` | `Circular_Saw` | Equipment Hazard |
| `6` | `No-Boots` | Violation State | `16` | `Fire_Extinguisher` | Safety Equipment |
| `7` | `No-Ear-Protection`| Violation State | `17` | `Fire_prevention_Net`| Work-at-Height Net |
| `8` | `No-Glass` | Violation State | `18` | `Welding_Equipment` | Hot-Work Hazard |
| `9` | `No-Glove` | Violation State | | | |

---

## 🚀 Training Instructions

### 1. Local Workstation Training (CUDA GPU)
```bash
python training/train_model.py \
    --data data.yaml \
    --epochs 100 \
    --imgsz 640 \
    --batch 16 \
    --device 0
```

### 2. Cloud GPU Training (Kaggle / Colab)
1. Mount the dataset `Construction PPE Detection Combined.yolov8`.
2. Run `training/kaggle_export/kaggle_training.py` with GPU T4/P100 enabled.
3. Download the generated `best.pt` weights and place them into `models/best.pt`.