# Training – EdgeVision PPE Model

This folder contains everything needed to train and export the PPE detection model.
Once training is complete, copy `weights/best.pt` to the project root (or set `MODEL_PATH`
in your environment) and run the main application.

## Files

| File | Purpose |
|------|---------|
| `train_model.py` | Fine-tune YOLOv8 on the PPE dataset |
| `export_onnx.py` | Export trained `.pt` to portable ONNX format |
| `export_tensorrt.py` | Build TensorRT FP16 engine (Jetson only) |
| `dataset.yaml` | Dataset config – 8 PPE classes, relative paths |
| `colab_export/` | Google Colab training notebook / script |

## Quick start

```bash
# 1. Prepare dataset (see docs/dataset_guide.md)
#    Place images in datasets/ppe_dataset/images/{train,val,test}/
#    Place labels in datasets/ppe_dataset/labels/{train,val,test}/

# 2. Train (GPU recommended; 50 epochs default, 150+ for production)
python training/train_model.py --epochs 150 --imgsz 640

# 3. Export to ONNX (portable)
python training/export_onnx.py --model ppe_training/custom_model/weights/best.pt

# 4. Export to TensorRT (Jetson only — run ON the device)
python training/export_tensorrt.py --model ppe_training/custom_model/weights/best.pt

# 5. Point the runtime at your model
export MODEL_PATH=ppe_training/custom_model/weights/best.pt
# or best.engine for TensorRT


## Google Colab

Use `colab_export/colab_training.py` to train on a free T4 GPU.
The script mounts your Google Drive, installs dependencies, and saves
the best weights back to Drive automatically.

## Dataset classes (must match dataset.yaml)

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

See `../docs/dataset_guide.md` for the full labelling guide.

PPE detection system
Why Use ONNX as an Interchange FormatUniversal Bridge: Most models are trained in PyTorch or TensorFlow, which are heavy to run directly on edge devices. You first export your model to ONNX because it acts as a standard graph format supported by almost all deep learning training tools.Easy Conversion: Tools like torch.onnx.export or tf2onnx let you cleanly translate model weights and layout structures out of your training PC

Nvidia Jetson is a series of small, low-power computer boards made by Nvidia. It acts like a tiny supercomputer. It lets devices run artificial intelligence and machine learning programs right on the device without needing the internet or a cloud server

NVIDIA TensorRT is a software development kit (SDK) and high-performance deep learning inference optimizer created by NVIDIA. It takes trained neural networks from frameworks like PyTorch or TensorFlow, compiles them, and optimizes them to run with ultra-low latency and high throughput on NVIDIA GPUs