# 🏷️ Dataset Taxonomy & Annotation Engineering Guide

> **Repository:** [https://github.com/Vidhyasree14/Cerberus-AI](https://github.com/Vidhyasree14/Cerberus-AI) | **Developer:** Vidhyashree M

This technical guide outlines the PPE class taxonomy, directory layout, labeling standards, and data augmentation pipeline used to train **Cerberus AI**.

---

## 🏷️ PPE Detection Taxonomy

The custom YOLOv8 model is trained across two functional label categories:

### ✅ Compliant PPE Classes (Positive States)

| Class ID | Label | Detection Target |
| :---: | :--- | :--- |
| `0` | `Boots` | Safety footwear (steel-toed, ankle-high) |
| `1` | `Ear-Protection` | Earmuffs or in-ear hearing protection |
| `2` | `Glass` | Safety glasses or protective eyewear (clear/tinted) |
| `3` | `Glove` | Work gloves (latex, leather, cut-resistant) |
| `4` | `Hard_hat` | Construction-grade hard hat or bump cap |
| `5` | `Mask` | Dust mask, N95, or full-face respirator |

### 🚨 Violation State Classes (Absence Detections)

| Class ID | Label | Trigger Condition |
| :---: | :--- | :--- |
| `6` | `No-Boots` | Worker detected without safety footwear |
| `7` | `No-Ear-Protection` | Worker detected without hearing protection in noisy zone |
| `8` | `No-Glass` | Worker detected without eye protection |
| `9` | `No-Glove` | Worker detected with bare hands in hazard zone |
| `10` | `No-Helmet` | Worker detected without head protection |
| `11` | `No-Mask` | Worker detected without respiratory protection |
| `12` | `No-Vest` | Worker detected without high-visibility vest |

---

## 📁 YOLOv8 Directory Layout

```
datasets/ppe_industrial/
├── data.yaml                  # YOLO dataset configuration (class names, paths)
├── train/
│   ├── images/               # 70% Training frames (.jpg, .png) — ~6,500+ images
│   └── labels/               # Normalized YOLO format annotations (.txt)
├── valid/
│   ├── images/               # 20% Validation frames — ~1,800+ images
│   └── labels/               # Validation annotations
└── test/
    ├── images/               # 10% Unseen benchmark test frames — ~900+ images
    └── labels/               # Ground truth test labels
```

**`data.yaml` Format:**
```yaml
path: datasets/ppe_industrial
train: train/images
val: valid/images
test: test/images

nc: 13
names:
  - Boots
  - Ear-Protection
  - Glass
  - Glove
  - Hard_hat
  - Mask
  - No-Boots
  - No-Ear-Protection
  - No-Glass
  - No-Glove
  - No-Helmet
  - No-Mask
  - No-Vest
```

**YOLO Annotation Format (`.txt`):**
```
# <class_id> <x_center> <y_center> <width> <height>  (all normalized 0.0–1.0)
4  0.511 0.135 0.148 0.092    # Hard_hat bounding box
0  0.515 0.890 0.142 0.080    # Boots bounding box
```

---

## 🌐 Dataset Source

The model was trained on the **Construction PPE Detection Combined** dataset (YOLOv8 format), covering diverse industrial and construction site environments:

- **Environments:** Indoor plant floors, outdoor construction sites, rooftop work-at-height platforms, welding stations
- **Lighting Conditions:** Bright daylight, overcast, fluorescent industrial, low-light night shift
- **Camera Angles:** Frontal, side profile, overhead CCTV, diagonal
- **Frame Resolution:** Mixed — 640×480, 1280×720, 1920×1080 (all resized to 640×640 for training)

---

## 🧪 Augmentation & Robustness Strategies

The following augmentation pipeline was applied during training to maximize generalization across industrial environments:

| Augmentation | Technique | Target Problem Solved |
| :--- | :--- | :--- |
| **Mosaic (4-image)** | Stitches 4 training images into one composite | Small object detection (`Glass`, `Ear-Protection`, `Glove`) |
| **CLAHE Contrast Jitter** | Random contrast enhancement via CLAHE | Heavy indoor shadows, welding arc flash, low-light shifts |
| **Random Horizontal Flip** | 50% probability flip | Camera orientation invariance |
| **Scale Jitter** | ±50% random scale variation | Workers at varying distances from camera |
| **HSV Color Augmentation** | Hue ±1.5%, Sat ±70%, Val ±40% | Vest/glove color variation across manufacturers |
| **Occlusion & Cutout** | Random masking of body regions | Anatomical association robustness behind equipment |
| **Hard Negative Mining** | PPE placed on benches, not worn | Suppress false-positive associations |
| **MixUp Blending** | Alpha = 0.1 blending of frame pairs | Boundary confidence calibration |
| **Rotation (±10°)** | Slight random rotation | Camera tilt compensation |

---

## 📐 Annotation Standards & Quality Guidelines

### Bounding Box Rules

- **Worker boxes** must encompass the full visible body — head to foot or ground-level cutoff.
- **PPE boxes** must tightly bound only the item itself, not surrounding body region.
- **Minimum size:** No bounding box smaller than `15×15 pixels` at native resolution.
- **Overlap policy:** PPE boxes may partially overlap Worker boxes (expected and correct).

### Labeling Edge Cases

| Scenario | Correct Label |
| :--- | :--- |
| Worker partially occluded, but head visible and helmet present | Label `Hard_hat` + `Worker` |
| Helmet placed on workbench, not worn | Label `Hard_hat` only (no `Worker` association) |
| Worker facing away, vest clearly visible | Label `Vest` + `Worker` |
| Worker fully occluded by equipment | Skip frame / don't label `Worker` |
| PPE partially visible (>50% visible) | Label the PPE class |
| PPE <50% visible | Skip labeling that item |

---

## 📊 Dataset Statistics

| Split | Images | Total Annotations | Avg Annotations/Image |
| :--- | :---: | :---: | :---: |
| **Train** | ~6,500 | ~38,200 | 5.9 |
| **Validation** | ~1,800 | ~10,600 | 5.9 |
| **Test** | ~900 | ~5,300 | 5.9 |
| **Total** | **~9,200** | **~54,100** | **5.9** |

---

*Part of the [Cerberus AI](https://github.com/Vidhyasree14/Cerberus-AI) platform — developed by Vidhyashree M.*
