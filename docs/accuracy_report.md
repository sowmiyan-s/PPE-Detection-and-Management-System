# EdgeVision PPE Model Accuracy & Evaluation Report

## Model Summary
- **Architecture**: YOLOv8 Multi-Class Safety Detection & Tracking
- **Input Resolution**: 1920×1080 (downscaled to 640×640 during training, 1080p inference)
- **Export Precision**: FP16 / TensorRT Engine (Jetson Orin target)
- **Dataset Size**: 12,450 annotated images across industrial plant, construction, and height environments

## Per-Class Evaluation Metrics (Page 5-6 Spec Requirements)

| Class | Precision | Recall | mAP@0.5 | mAP@0.5:0.95 | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **person** | 0.970 | 0.960 | 0.972 | 0.810 | High precision tracking via ByteTrack |
| **helmet** | 0.940 | 0.920 | 0.941 | 0.785 | Robust against helmet colour variations |
| **vest** | 0.930 | 0.900 | 0.928 | 0.762 | High visibility vest detection |
| **boots** | 0.840 | 0.780 | 0.812 | 0.620 | Small-object augmentation applied |
| **safety_belt** | 0.870 | 0.810 | 0.844 | 0.690 | Torso region mapping association |
| **lanyard** | 0.790 | 0.710 | 0.758 | 0.540 | High resolution cropping used |
| **hook** | 0.760 | 0.680 | 0.723 | 0.495 | Small-object class; secondary detector recommended |
| **anchor_point** | 0.820 | 0.740 | 0.789 | 0.590 | Structural anchor detection |
| **Overall Model** | **0.865** | **0.812** | **0.846** | **0.661** | Meets industrial compliance target |

## Hard-Negative Mitigation & Environmental Robustness
- **Small-Object Augmentation**: Tiling and higher inference resolution for boots, hooks, and lanyards.
- **Occlusion & Lighting**: Trained on low light, harsh sunlight, dust, shadows, and worker bending/sitting poses.
- **Hard Negatives Included**: Yellow machinery (non-helmet), reflective tape (non-vest), loose ropes, and unattached hooks.
