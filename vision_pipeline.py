import cv2
from ultralytics import YOLO
from association import associate_ppe_to_persons

class VisionPipeline:
    def __init__(self, model_path="ppe_training/custom_model/weights/best.pt", ppe_classes=None):
        # Initialize the YOLO model. 
        # For actual PPE detection, we are using the custom trained model weights ('best.pt').
        self.model = YOLO(model_path)
        
        # List of classes that represent safety equipment
        self.ppe_classes = ppe_classes or [
            "helmet_worn_properly", "helmet_worn_improperly", "no_helmet", 
            "safety_vest", "safety_boots", "safety_hook", "helmet", "vest", "boots"
        ]
        
    def process_frame(self, frame):
        """
        Runs YOLO tracking on the frame, extracts persons and PPE, associates them, 
        and prepares the data payload for the dashboard.
        """
        # Run YOLO with tracking enabled. 'bytetrack.yaml' enables ByteTrack.
        results = self.model.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False)
        
        if not results or len(results) == 0:
            return frame, []
            
        result = results[0]
        boxes = result.boxes
        
        persons = []
        ppe_items = []
        
        if boxes is not None:
            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                class_name = self.model.names[cls_id]
                box = boxes.xyxy[i].tolist()
                conf = float(boxes.conf[i].item())
                
                # If it's a person and has a tracking ID assigned by ByteTrack
                if class_name == "person" and boxes.id is not None:
                    try:
                        track_id = int(boxes.id[i].item())
                        persons.append({
                            'id': track_id,
                            'box': box,
                            'class_name': class_name
                        })
                    except Exception:
                        pass
                # If it's another class, treat as PPE
                elif class_name in self.ppe_classes:
                    ppe_items.append({
                        'box': box,
                        'class_name': class_name,
                        'confidence': conf
                    })
        
        # Associate detected PPE to tracked persons
        person_ppe_map = associate_ppe_to_persons(persons, ppe_items)
        
        # Format the output data for the dashboard
        dashboard_data = []
        for person in persons:
            p_id = person['id']
            ppes = person_ppe_map.get(p_id, [])
            dashboard_data.append({
                "person_id": p_id,
                "equipment": [p['class_name'] for p in ppes]
            })
            
            # Draw bounding box for person on the video frame
            x1, y1, x2, y2 = map(int, person['box'])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"Person ID: {p_id}", (x1, y1 - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        
        # Draw bounding boxes for PPE
        for ppe in ppe_items:
            x1, y1, x2, y2 = map(int, ppe['box'])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
            cv2.putText(frame, f"{ppe['class_name']} {ppe['confidence']:.2f}", (x1, y1 - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                        
        return frame, dashboard_data
