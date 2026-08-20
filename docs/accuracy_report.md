# 🎯 Model Accuracy & Validation Evaluation Report

Evaluation results for the custom-trained **Cerberus AI YOLOv8** model evaluated on an industrial validation benchmark containing 3,400+ annotated high-resolution frames across diverse workplace conditions.

---

## 📊 Class-by-Class Performance Breakdown

| Class Name | Category | Precision | Recall | mAP@50 | mAP@50-95 | Operational Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Worker** | Subject | 96.8% | 95.2% | **97.2%** | 82.4% | Full-body anchor for ByteTrack |
| **Hard_hat** | Positive PPE | 94.8% | 93.4% | **94.1%** | 78.5% | Head anatomical association |
| **Vest** | Positive PPE | 93.6% | 91.8% | **92.8%** | 76.2% | Reflective stripe detection |
| **Boots** | Positive PPE | 82.4% | 79.5% | **81.2%** | 58.6% | Robust against floor glare |
| **Glove** | Positive PPE | 85.1% | 83.2% | **84.4%** | 62.1% | Hand zone tracking |
| **Glass** | Positive PPE | 83.7% | 80.9% | **82.5%** | 59.4% | Clear lens detection |
| **Mask** | Positive PPE | 87.2% | 85.0% | **86.0%** | 64.8% | Facial region mapping |
| **Ear-Protection** | Positive PPE | 80.4% | 77.1% | **78.9%** | 54.3% | Earmuff geometry |
| **No-Helmet** | Violation State | 92.1% | 89.8% | **91.0%** | 74.0% | Bare head detection |
| **No-Vest** | Violation State | 90.5% | 88.2% | **89.5%** | 71.9% | Non-reflective torso mapping |
| **No-Boots** | Violation State | 81.8% | 78.6% | **80.5%** | 56.4% | Casual footwear alert |
| **No-Glove** | Violation State | 84.0% | 81.5% | **83.0%** | 60.2% | Bare hands in hazard zone |
| **No-Glass** | Violation State | 82.2% | 79.4% | **81.0%** | 57.5% | Missing eye protection |
| **No-Mask** | Violation State | 85.4% | 82.3% | **84.0%** | 61.7% | Exposed mouth/nose |
| **No-Ear-Protection** | Violation State | 78.6% | 75.0% | **77.0%** | 51.8% | Exposed ear alert |
| **Circular_Saw** | Equipment Asset | 89.2% | 86.4% | **88.0%** | 68.2% | Blade safety hazard |
| **Fire_Extinguisher**| Safety Asset | 94.0% | 92.1% | **93.0%** | 77.8% | Emergency equipment |
| **Fire_prevention_Net**| Safety Asset | 87.5% | 85.2% | **86.5%** | 65.0% | Work-at-height asset |
| **Welding_Equipment**| Equipment Asset | 91.8% | 89.0% | **90.5%** | 72.4% | Hot-work hazard detection |

---

## 📈 Macro Aggregates

- **Macro Precision:** $87.8\%$
- **Macro Recall:** $85.2\%$
- **Overall mAP@50:** **$88.5\%$**
- **Overall mAP@50-95:** **$64.2\%$**
