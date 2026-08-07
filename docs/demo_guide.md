# EdgeVision Live & Recorded Demonstration Guide

This guide provides step-by-step instructions for demonstrating the **EdgeVision PPE Compliance and Work-at-Height Safety Platform** live or via recorded video clips.

## 1. Quick Start Demonstration

### Start Fullstack Application
Execute the one-click startup script:
```cmd
C:\Users\Asus\Desktop\test\start_fullstack.bat
```
This automatically launches:
1. **FastAPI Backend Server**: Running on `http://localhost:8000` (WebSockets on `/ws`).
2. **React / TanStack Dashboard**: Running on `http://localhost:5173`.

---

## 2. Demonstrating Dashboard Pages (PDF Spec Pages 4-5)

Navigate through the navigation bar on `http://localhost:5173`:

1. **Control Room Overview (`/`)**:
   - Demonstrates live pipeline health, FPS throughput indicator, 7-day violation trends, and camera status.
2. **Live Monitoring (`/live`)**:
   - Shows the 6-camera industrial grid overlaying real-time YOLOv8 bounding boxes, persistent worker IDs, and compliance tags on `CAM-01`.
3. **Active Violations (`/violations`)**:
   - Displays real-time unacknowledged compliance alerts filtered by zone and violation type.
4. **Event History (`/events`)**:
   - Shows searchable historical violation records with image evidence and video clips.
5. **Worker Compliance (`/compliance`)**:
   - Displays tracking IDs (`Worker-101`, `Worker-102`), shift information, compliance percentages, and total hours tracked.
6. **Zone Configuration (`/zones`)**:
   - Allows switching safety zones (`general_plant`, `construction`, `work_at_height`, `restricted_machinery`) and configuring required PPE items per zone.
7. **Camera Management (`/cameras`)**:
   - Displays camera resolution, FPS, latency, and RTSP stream status.
8. **Reports (`/reports`)**:
   - Displays daily, weekly, and monthly industrial safety compliance metrics.
9. **Model Monitoring (`/model`)**:
   - Shows model version (`edgevision-v3.2-fp16`), class-by-class precision/recall metrics, and P95 inference latency.

---

## 3. Demonstrating 5-Stage Vision Pipeline Logic

To demonstrate pipeline execution in terminal:
```bash
python src/core/detector.py 0 work_at_height
```
This opens OpenCV frame capture, demonstrating:
- **Stage 1**: Person detection and ByteTrack tracking (`Worker-101`).
- **Stage 2**: PPE detection (helmet, vest, boots, safety_belt, lanyard, hook).
- **Stage 3**: Person-to-PPE association (head, torso, feet body-region mapping).
- **Stage 4**: Rule engine evaluation.
- **Stage 5**: Temporal validation (suppressing single-frame noise).
