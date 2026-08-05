from ultralytics import YOLO

def train_and_export(data_yaml: str, epochs: int = 100, batch_size: int = 16, imgsz: int = 640, device: int = 0):
    """
    Trains a YOLO model with custom augmentations for industrial environments and exports it to TensorRT.
    
    Args:
        data_yaml (str): Path to the dataset YAML file.
        epochs (int): Number of training epochs.
        batch_size (int): Batch size.
        imgsz (int): Image size.
        device (int): GPU device ID.
    """
    # Initialize YOLOv8 Nano model (can be replaced with YOLOv11 if available/preferred)
    print("Loading YOLOv8n model...")
    model = YOLO('yolov8n.pt')
    
    print(f"Starting training on {data_yaml} for {epochs} epochs...")
    # Train the model with heavy industrial augmentations
    model.train(
        data=data_yaml,
        epochs=epochs,
        batch=batch_size,
        imgsz=imgsz,
        device=device,
        # Augmentations
        mosaic=1.0,
        mixup=0.15,
        hsv_v=0.4,    # For shadows/low light
        degrees=10.0,
        # Other hyperparams could be added here
    )
    
    print("Training complete. Exporting model to TensorRT (FP16)...")
    # Export the trained model to TensorRT format with FP16 precision
    try:
        exported_path = model.export(
            format="engine",
            half=True,       # FP16 precision
            device=device,   # TensorRT export requires a GPU
            imgsz=imgsz,
            workspace=4      # GB of workspace
        )
        print(f"Successfully exported TensorRT engine to: {exported_path}")
    except Exception as e:
        print(f"TensorRT export failed. Please ensure NVIDIA drivers, CUDA, and TensorRT are installed. Error: {e}")

if __name__ == "__main__":
    # Example usage. Replace 'dataset.yaml' with your actual dataset config file.
    import argparse
    parser = argparse.ArgumentParser(description="Train and export YOLO model for PPE Detection.")
    parser.add_argument("--data", type=str, default="dataset.yaml", help="Path to data.yaml")
    parser.add_argument("--epochs", type=int, default=100, help="Number of epochs")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--imgsz", type=int, default=640, help="Image size")
    
    args = parser.parse_args()
    
    train_and_export(
        data_yaml=args.data,
        epochs=args.epochs,
        batch_size=args.batch,
        imgsz=args.imgsz
    )
