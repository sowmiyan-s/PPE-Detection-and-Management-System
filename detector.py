import cv2
import numpy as np
import torch
import ultralytics
from ultralytics import YOLO
from enhancer import IndustrialImageEnhancer
from publisher import PPEMqttPublisher

# Fix for PyTorch 2.6 weights_only=True default
if hasattr(torch.serialization, 'add_safe_globals'):
    try:
        torch.serialization.add_safe_globals([ultralytics.nn.tasks.DetectionModel])
    except Exception:
        pass

class PPEDetector:
    def __init__(self, model_path="yolov8n.pt", mqtt_broker="localhost", mqtt_port=1883):
        """
        Initializes the PPE Compliance Engine.
        Args:
            model_path (str): Path to the YOLOv8 model weights (e.g., .pt or .engine).
            mqtt_broker (str): MQTT broker address for publishing alerts.
            mqtt_port (int): MQTT broker port.
        """
        print(f"Loading model from {model_path}...")
        self.model = YOLO(model_path)
        self.enhancer = IndustrialImageEnhancer()
        self.publisher = PPEMqttPublisher(broker=mqtt_broker, port=mqtt_port)
        
        # Define the target PPE items required for compliance.
        # This assumes the trained YOLO model uses these exact class names.
        self.REQUIRED_PPE = {'helmet', 'vest', 'boots', 'safety_hook'}
        
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Processes a single frame: enhances it, tracks workers, matches PPE, 
        evaluates compliance, sends alerts, and draws annotations.
        """
        # 1. Enhance the image for low-light/dust
        enhanced_frame = self.enhancer.enhance(frame)
        
        # 2. Run YOLO inference & tracking
        # conf=0.20 retains tracks even when visibility drops
        results = self.model.track(
            enhanced_frame,
            persist=True,
            tracker="bytetrack.yaml",
            conf=0.20,
            verbose=False
        )
        
        if not results or len(results) == 0:
            return enhanced_frame
            
        result = results[0]
        boxes = result.boxes
        
        if boxes is None or len(boxes) == 0:
            return enhanced_frame

        # 3. Extract entities
        persons = []
        ppes = []
        
        for i in range(len(boxes)):
            box = boxes[i].xyxy[0].cpu().numpy()
            conf = float(boxes[i].conf[0].cpu().numpy())
            cls_id = int(boxes[i].cls[0].cpu().numpy())
            cls_name = result.names[cls_id]
            
            if cls_name == 'person':
                track_id = int(boxes[i].id[0].cpu().numpy()) if boxes[i].id is not None else -1
                persons.append({'id': track_id, 'box': box, 'conf': conf})
            elif cls_name in self.REQUIRED_PPE:
                # Calculate center point (cx, cy)
                x1, y1, x2, y2 = box
                cx = (x1 + x2) / 2.0
                cy = (y1 + y2) / 2.0
                ppes.append({'name': cls_name, 'cx': cx, 'cy': cy})

        # 4. Evaluate compliance via Spatial Matching Logic
        for person in persons:
            x1, y1, x2, y2 = person['box']
            track_id = person['id']
            conf = person['conf']
            
            if track_id == -1:
                # If the tracker hasn't assigned an ID yet, we can't reliably track state over frames
                continue
                
            worker_id = f"Worker_{track_id}"
            person_ppes = set()
            
            # Check if PPE centers are inside the worker's bounding box
            for ppe in ppes:
                if x1 <= ppe['cx'] <= x2 and y1 <= ppe['cy'] <= y2:
                    person_ppes.add(ppe['name'])
                    
            missing_equipment = list(self.REQUIRED_PPE - person_ppes)
            is_compliant = len(missing_equipment) == 0
            
            # 5. Alert Publisher (Decoupled MQTT logic handles the >3 consecutive frame rule)
            self.publisher.process_worker_state(
                worker_id=worker_id,
                is_compliant=is_compliant,
                missing_equipment=missing_equipment,
                confidence_score=conf
            )
            
            # 6. Annotate Frame
            color = (0, 255, 0) if is_compliant else (0, 0, 255)
            cv2.rectangle(enhanced_frame, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
            
            # Draw Worker ID and Status
            label = f"{worker_id} [{conf:.2f}]"
            cv2.putText(enhanced_frame, label, (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
            if not is_compliant:
                missing_str = "Missing: " + ", ".join(missing_equipment)
                cv2.putText(enhanced_frame, missing_str, (int(x1), int(y2) + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            else:
                cv2.putText(enhanced_frame, "COMPLIANT", (int(x1), int(y2) + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
        return enhanced_frame

    def release(self):
        """Cleanup resources."""
        self.publisher.close()

if __name__ == "__main__":
    # Test script for detector
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=str, default="0", help="Video source (0 for webcam, or file path)")
    args = parser.parse_args()
    
    # Try using public test broker for local run, if not localhost
    detector = PPEDetector(mqtt_broker="test.mosquitto.org")
    
    source = int(args.source) if args.source.isdigit() else args.source
    cap = cv2.VideoCapture(source)
    
    print("Starting video processing... Press 'q' to quit.")
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        processed_frame = detector.process_frame(frame)
        cv2.imshow("PPE Compliance Surveillance", processed_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
    cap.release()
    cv2.destroyAllWindows()
    detector.release()
