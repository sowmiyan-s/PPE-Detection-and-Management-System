# 1. Mount your Google Drive
from google.colab import drive
drive.mount('/content/drive')

# 2. Install YOLOv8
import os
os.system('pip install ultralytics')

# 3. Copy your dataset and config file from Drive into Colab's fast memory
os.system('cp "/content/drive/MyDrive/ppe_dataset.zip" "/content/"')
os.system('cp "/content/drive/MyDrive/dataset.yaml" "/content/"')

# 4. Unzip the dataset
os.system('unzip -q /content/ppe_dataset.zip -d /content/')

# 5. Start Training!
from ultralytics import YOLO
model = YOLO('yolov8n.pt') 

print("Starting training on Google Colab T4 GPU...")
results = model.train(
    data='/content/dataset.yaml', 
    epochs=50, 
    imgsz=640,
    batch=16, # The Colab T4 GPU has 16GB VRAM, so batch=16 is perfect!
    project='/content/drive/MyDrive/ppe_training', 
    name='custom_model'
)

print("Training finished! The best weights are saved in your Google Drive at: ppe_training/custom_model/weights/best.pt")
