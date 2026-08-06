import torch
import ultralytics
from ultralytics import YOLO

# Fix for PyTorch 2.6 weights_only=True default breaking YOLO loading
_original_load = torch.load
def safe_load(*args, **kwargs):
    kwargs['weights_only'] = False
    return _original_load(*args, **kwargs)
torch.load = safe_load

# Strict cuDNN configuration to prevent CUDNN_STATUS_EXECUTION_FAILED and nan loss
torch.backends.cudnn.enabled = True
torch.backends.cudnn.benchmark = False
torch.backends.cudnn.deterministic = True

def main():
    # 1. Load a pretrained model (YOLOv8 Nano is HIGHLY recommended for Jetson)
    print("Loading YOLOv8n base model...")
    model = YOLO("yolov8n.pt")  # 'n' is nano: crucial for real-time FPS on Jetson hardware
    
    # 2. Train the model
    # NOTE: Ensure you have your dataset ready and the data.yaml path is correct.
    print("Starting training process...")
    results = model.train(
        data="dataset.yaml",       # Path to your dataset's YAML configuration file
        epochs=50,              # Number of training epochs (increase to 100-300 for production accuracy)
        imgsz=640,              # Standard YOLO image size
        batch=4,                # Lowered to 4 to guarantee no Out Of Memory on 4GB VRAM
        device=0,               # Set to '0' to use your NVIDIA GPU
        amp=False,              # MUST BE FALSE FOR GTX 1650 (fixes nan loss and cuDNN crashes)
        half=False,             # Disable FP16 entirely to avoid nan losses
        optimizer="SGD",        # SGD is significantly more stable than AdamW
        lr0=0.01,               # Stable learning rate for SGD
        workers=2,              # Limit dataloader workers to prevent RAM/Pagefile crashes on Windows
        project="ppe_training", # Folder name where results will be saved
        name="custom_model"     # Name of the specific training run
    )
    
    print("\nTraining complete!")
    print("Your new custom model weights are saved at: ppe_training/custom_model/weights/best.pt")

if __name__ == "__main__":
    main()
