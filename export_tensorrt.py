from ultralytics import YOLO
import sys
import os

def export_model(model_path="best.pt"):
    if not os.path.exists(model_path):
        print(f"Error: Could not find '{model_path}'.")
        print("Please ensure your model has finished training and you have copied the 'best.pt' file into this folder.")
        sys.exit(1)

    print(f"Loading YOLO model from {model_path}...")
    model = YOLO(model_path)
    
    print("Exporting model to TensorRT Engine format for NVIDIA Jetson...")
    print("This might take a few minutes. Please wait...")
    
    # Export to TensorRT. 'half=True' uses FP16 precision which makes it significantly faster on Jetson GPUs
    # without a noticeable drop in accuracy.
    model.export(format="engine", half=True, device=0) 
    
    print("\nExport complete!")
    print("You should now see a 'best.engine' file in your folder.")
    print("Update server.py to use 'VisionPipeline(\"best.engine\")' and restart the server!")

if __name__ == "__main__":
    # If they pass a custom path, use it, otherwise default to best.pt
    path = sys.argv[1] if len(sys.argv) > 1 else "best.pt"
    export_model(path)
