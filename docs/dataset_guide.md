# PPE Dataset Structure and Labelling Guide

## Directory Layout

```
datasets/ppe_dataset/
├── images/
│   ├── train/      ← training images (.jpg or .png)
│   ├── val/        ← validation images
│   └── test/       ← held-out test images (optional)
└── labels/
    ├── train/      ← YOLO label files (.txt)
    ├── val/
    └── test/
```

Each image file must have a matching `.txt` label file with the same base name.

---

## Label Format

Each line in a `.txt` file describes one bounding box:

```
<class_id> <cx> <cy> <width> <height>
```

- All values are **normalised** to `[0, 1]` relative to image width/height.
- `cx`, `cy` are the **centre** of the bounding box (not top-left).

**Example** (640 × 480 image, helmet at pixel box [120, 30, 280, 110]):
```
1 0.3125 0.1458 0.3333 0.1667
```

---

## Class IDs

| ID | Name | Detection requirement |
|----|------|----------------------|
| 0 | `person` | Person identification and tracking |
| 1 | `helmet` | Safety helmet – present, absent, or incorrectly worn |
| 2 | `vest` | Reflective safety vest – present or absent |
| 3 | `boots` | Safety boots – present or absent |
| 4 | `safety_belt` | Safety harness/belt – present or absent |
| 5 | `lanyard` | Lanyard – connected or disconnected |
| 6 | `hook` | Safety hook – present and connected appropriately |
| 7 | `anchor_point` | Fixed anchor point for lanyard |

---

## Recommended Labelling Tools

- **[Label Studio](https://labelstud.io/)** – open-source, supports YOLO export
- **[Roboflow](https://roboflow.com/)** – cloud-based, supports augmentation and YOLO export
- **[CVAT](https://cvat.org/)** – open-source, professional-grade
- **[labelImg](https://github.com/HumanSignal/labelImg)** – lightweight, desktop app

Export format: **YOLOv8 (txt)** from any of the above.

---

## Dataset Size Guidelines

| Stage | Minimum images | Recommended |
|-------|---------------|-------------|
| Proof of concept | 300 / class | 500 / class |
| Production | 1 000 / class | 3 000+ / class |

Class distribution should be balanced. Helmet and vest are easier to collect;
boots, hooks, and lanyards require deliberate effort at varied camera angles.

---

## Required Scene Diversity

To achieve robust detection across industrial environments, the dataset **must** include:

### Environmental conditions
- Low light (dusk, poorly lit areas)
- Harsh sunlight / backlight
- Shadows and partial shade
- Dust and haze
- Motion blur (workers in motion)

### Worker poses and positions
- Standing, walking, crouching, sitting
- Workers facing away from camera
- Workers bending over
- Partial visibility / occlusion
- Crowded scenes (≥ 5 workers in frame)

### PPE appearance variation
- Different helmet colours (white, yellow, red, blue, green)
- Different vest colours and patterns
- Different boot styles
- Helmets worn at different angles (tilted, pushed back)
- PPE held in hand but not worn (hard-negative)

### Hard-negative examples (must include)

These prevent common false detections:

| False detection | Hard-negative to include |
|----------------|--------------------------|
| Yellow machinery → helmet | Machinery without workers |
| Reflective surfaces → vest | Safety tape, painted lines |
| Regular shoes → boots | Workers in trainers |
| Loose ropes → lanyard | Ropes, cables not attached to worker |
| Hooks nearby → connected hook | Hooks lying on ground |

---

## Recommended Split

| Split | Proportion | Purpose |
|-------|-----------|---------|
| `train` | 70 % | Model training |
| `val` | 20 % | Hyperparameter tuning, early stopping |
| `test` | 10 % | Final evaluation (do not use during training) |

---

## Quality Checklist

Before training:
- [ ] Every image has a corresponding label file (including empty `.txt` for images with no objects)
- [ ] All class IDs are in range 0–7
- [ ] Bounding boxes are tight (≤ 5 px padding)
- [ ] Helmets worn incorrectly are labelled `helmet` (not a separate class)
- [ ] No duplicate images between train/val/test
- [ ] Hard-negative scenes are included (≥ 10 % of train set)
- [ ] `dataset.yaml` paths are correct and relative to the project root
- [ ] `nc: 8` in `dataset.yaml`

---

## ONNX / TensorRT Calibration Data

For INT8 TensorRT export, collect a representative calibration set:
- 200–500 diverse images from the training set
- Place them in `datasets/calibration/`
- Pass the path to the TensorRT builder (see `docs/tensorrt_instructions.md`)
