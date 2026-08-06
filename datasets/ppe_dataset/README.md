# PPE Dataset

Place your labelled dataset here following this structure:

```
datasets/ppe_dataset/
├── images/
│   ├── train/          ← training images (.jpg or .png)
│   ├── val/            ← validation images
│   └── test/           ← held-out test images
└── labels/
    ├── train/          ← YOLO label files (.txt, one per image)
    ├── val/
    └── test/
```

## Label format

Each `.txt` file contains one line per object:
```
<class_id> <cx> <cy> <width> <height>
```
All values normalised to `[0, 1]`. See `docs/dataset_guide.md` for the full guide.

## Class IDs

| ID | Class |
|----|-------|
| 0 | person |
| 1 | helmet |
| 2 | vest |
| 3 | boots |
| 4 | safety_belt |
| 5 | lanyard |
| 6 | hook |
| 7 | anchor_point |

## Recommended sources

- [Roboflow Universe – PPE Detection](https://universe.roboflow.com/search?q=ppe)
- [Kaggle – Hard Hat Workers Dataset](https://www.kaggle.com/datasets/andrewmvd/hard-hat-workers)
- Custom site footage labelled with Label Studio or CVAT
