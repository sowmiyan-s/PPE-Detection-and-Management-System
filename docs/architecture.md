# EdgeVision Platform Architecture Documentation

## 1. System Architecture

The EdgeVision platform combines a multi-stage YOLOv8 computer vision pipeline with a FastAPI backend server, MongoDB Atlas database, Mosquitto MQTT broker, and a TanStack Router React dashboard frontend.

```mermaid
flowchart TD
    Cam[Video Stream / Webcam / YouTube] --> Dec[OpenCV Video Capture]
    Dec --> Enh[Industrial Image Enhancer]
    Enh --> Yolo[Stage 1+2: YOLOv8 & ByteTrack]
    Yolo --> Assoc[Stage 3: Person-to-PPE Association]
    Assoc --> Rules[Stage 4: Zone Rule Engine]
    Rules --> Temp[Stage 5: Temporal Validator]
    
    Temp -- New Alert --> DB[(MongoDB Atlas)]
    Temp -- Evidence --> Store[database/evidence (JPG & MP4)]
    Temp -- MQTT Event --> Broker[Mosquitto MQTT Broker]
    
    FastAPI[FastAPI Server] <--> DB
    FastAPI <--> WS[WebSocket Streaming /ws]
    WS <--> UI[React + Vite Frontend]
```

---

## 2. Multi-Stage Computer Vision Pipeline

1. **Stage 1: Person Detection & Tracking**
   - Detects worker bounding boxes and tracks them across consecutive frames using ByteTrack. Assigns persistent tracking IDs (`Worker-101`).

2. **Stage 2: Multi-Class PPE Detection**
   - Identifies 7 safety equipment classes (`helmet`, `vest`, `boots`, `safety_belt`, `lanyard`, `hook`, `anchor_point`).

3. **Stage 3: Person-to-PPE Association**
   - Body-region containment mapping:
     - Head region ($0-25\%$) $\rightarrow$ `helmet`
     - Torso region ($20-75\%$) $\rightarrow$ `vest`, `safety_belt`, `lanyard`, `hook`
     - Feet region ($65-100\%$) $\rightarrow$ `boots`

4. **Stage 4: Zone-based Rule Engine**
   - Evaluates worker equipment against dynamic zone safety requirements:
     - **General Plant**: Helmet + Vest
     - **Construction**: Helmet + Vest + Boots
     - **Work at Height**: Helmet + Vest + Boots + Safety Belt + Hook
     - **Restricted Machinery**: Authorised Worker Check + Helmet + Vest

5. **Stage 5: Temporal Validator & Debouncer**
   - Requires violation hits in $8 / 10$ sliding window frames and minimum $2.0\text{s}$ zone duration before triggering an alert. Suppresses duplicate ongoing alerts.

---

## 3. Database Schema Design (MongoDB)

- `violation_events`: Incident evidence records (id, zone_id, worker_track_id, detected_ppe, missing_ppe, confidence, timestamp, image_base64, video_path, acknowledgement_status).
- `cameras`: Video stream configuration (id, name, source, zone_id, target_fps, status).
- `zones`: Configured safety zones & required PPE sets.
- `users` & `roles`: User accounts and permission roles.
- `audit_logs`: Event audit trails.
- `alert_deliveries`: Dispatch log for MQTT and webhook alerts.
