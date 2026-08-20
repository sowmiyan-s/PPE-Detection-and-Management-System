# 🏷️ Dataset Taxonomy & Annotation Engineering Guide

This technical guide outlines the 19-class taxonomy, directory layout, labeling standards, and data augmentation pipeline used to train **Cerberus AI**.

---

## 🏷️ 19-Class Industrial Taxonomy

```
[0] Boots             [5] Mask                 [10] No-Helmet           [15] Circular_Saw
[1] Ear-Protection    [6] No-Boots             [11] No-Mask             [16] Fire_Extinguisher
[2] Glass             [7] No-Ear-Protection    [12] No-Vest             [17] Fire_prevention_Net
[3] Glove             [8] No-Glass             [13] Worker              [18] Welding_Equipment
[4] Hard_hat          [9] No-Glove             [14] Vest
```

---

## 📁 YOLOv8 Directory Layout

```
datasets/ppe_industrial/
├── data.yaml                 # YOLO dataset configuration
├── train/
│   ├── images/              # 70% Training frames (.jpg, .png)
│   └── labels/              # Normalised YOLO format annotations (.txt)
├── valid/
│   ├── images/              # 20% Validation frames
│   └── labels/              # Validation annotations
└── test/
    ├── images/              # 10% Unseen benchmark test frames
    └── labels/              # Ground truth test labels
```

---

## 🧪 Augmentation & Robustness Strategies

1. **Mosaic Augmentation (4-Image Stitching):** Enhances detection of small objects (`Glass`, `Ear-Protection`, `Glove`) across varied spatial scales.
2. **CLAHE Contrast Jitter:** Simulates heavy indoor shadows, welding flash, and low-light night shifts.
3. **Occlusion & Cutout:** Randomly masks parts of worker bodies to train anatomical association robustness.
4. **Hard Negative Mining:** Annotates un-worn PPE placed on workbenches to suppress false-positive association.
