# TensorRT Engine Generation Instructions

## Prerequisites

These steps must be performed **on the target Jetson device** (or an
identically configured machine).  TensorRT engines are hardware- and
software-version specific.

### Required software (Jetson)

| Component | Version |
|-----------|---------|
| JetPack | 6.x (L4T R36) |
| CUDA | 12.2 |
| TensorRT | 8.6 or 10.x (bundled with JetPack) |
| Python | 3.10 |
| ultralytics | ≥ 8.2 |

Verify installed versions:
```bash
dpkg -l | grep -E "tensorrt|cuda|cudnn"
python3 -c "import tensorrt; print(tensorrt.__version__)"
```

---

## Step 1 – Train and export to ONNX (development machine)

```bash
# Train (development machine or cloud GPU)
python train_model.py --epochs 150 --imgsz 640

# Export to ONNX (portable format)
python export_onnx.py --model ppe_training/custom_model/weights/best.pt --imgsz 640
```

This produces: `ppe_training/custom_model/weights/best.onnx`

**Copy both `best.pt` and `best.onnx` to the Jetson device.**

---

## Step 2 – Generate FP16 TensorRT engine (on Jetson)

```bash
# On the Jetson device:
python export_tensorrt.py \
    --model ppe_training/custom_model/weights/best.pt \
    --imgsz 640 \
    --device 0
```

This calls `model.export(format="engine", half=True)` via Ultralytics,
which internally uses `trtexec` to build the engine.

Output: `ppe_training/custom_model/weights/best.engine`

Expect 5–15 minutes for first-time engine compilation.

---

## Step 3 – Verify the engine

```python
from ultralytics import YOLO
import cv2

model = YOLO("ppe_training/custom_model/weights/best.engine")
frame = cv2.imread("datasets/calibration/sample.jpg")
results = model(frame)
print(results[0].speed)   # preprocess / inference / postprocess ms
```

---

## Step 4 (Optional) – INT8 quantisation

INT8 delivers higher throughput but requires calibration data.

```bash
python export_tensorrt.py \
    --model ppe_training/custom_model/weights/best.pt \
    --imgsz 640 \
    --int8 \
    --device 0
```

Prepare calibration images in `datasets/calibration/` (200–500 images,
representative of deployment conditions).

---

## Step 5 – Use the engine in the server

```bash
export MODEL_PATH=ppe_training/custom_model/weights/best.engine
python server.py
```

Or set `MODEL_PATH` in your systemd environment file
(see `docs/jetson_setup.md`).

---

## Maintaining the engine for reproducibility

The `.engine` file is **not** the only deployable asset.  Maintain all of:

| Asset | Location |
|-------|----------|
| Training weights | `ppe_training/custom_model/weights/best.pt` |
| ONNX model | `ppe_training/custom_model/weights/best.onnx` |
| Calibration data | `datasets/calibration/` |
| Engine-generation command | This document |
| Exact JetPack / TensorRT versions | `docs/jetson_setup.md` |
| `dataset.yaml` | Project root |

Without these, the engine cannot be recreated if the Jetson is replaced or
the software stack is updated.

---

## FP16 vs INT8 comparison

| Metric | FP32 | FP16 | INT8 |
|--------|------|------|------|
| Accuracy | Baseline | ≈ baseline | Slight drop (~1–3 % mAP) |
| Throughput | 1× | ~2× | ~3–4× |
| Memory | Highest | Medium | Lowest |
| Calibration | Not needed | Not needed | Required |

**Recommendation:** Start with FP16. Use INT8 only if FP16 cannot reach
12 FPS at 1080p.

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `TensorRT version mismatch` | Engine built on different TRT version | Rebuild engine on same device |
| `CUDA out of memory` | Large batch or image size | Reduce `--imgsz` or `--batch` |
| `trtexec not found` | TensorRT not installed | Install TensorRT via JetPack SDK Manager |
| `segmentation fault during export` | Ultralytics + TRT version mismatch | Pin `ultralytics==8.2.x` and rebuild |
