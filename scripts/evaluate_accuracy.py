"""
EdgeVision Per-Class Accuracy Evaluation Script
Calculates Precision, Recall, mAP50, and mAP50-95 per PPE safety class.
"""

import argparse
import os
import sys

def evaluate_model(model_path: str = "models/best.pt", data_yaml: str = "data.yaml"):
    try:
        from ultralytics import YOLO
    except ImportError:
        print("Ultralytics required for validation. Run: pip install ultralytics")
        sys.exit(1)

    if not os.path.exists(model_path):
        print(f"Error: Model file {model_path} not found.")
        sys.exit(1)

    print(f"--- Running Accuracy Evaluation on {model_path} ---")
    model = YOLO(model_path)
    
    metrics = model.val(data=data_yaml, split="val")

    print("\n================== ACCURACY METRICS REPORT ==================")
    print(f"Overall mAP50    : {metrics.box.map50:.4f}")
    print(f"Overall mAP50-95 : {metrics.box.map:.4f}")
    print(f"Mean Precision   : {metrics.box.mp:.4f}")
    print(f"Mean Recall      : {metrics.box.mr:.4f}")
    print("============================================================\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate EdgeVision PPE Model Accuracy")
    parser.add_argument("--model", type=str, default="models/best.pt", help="Path to weights file")
    parser.add_argument("--data", type=str, default="data.yaml", help="Dataset configuration YAML")
    args = parser.parse_args()

    evaluate_model(args.model, args.data)
