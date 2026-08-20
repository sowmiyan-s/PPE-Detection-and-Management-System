# 🎬 Cerberus AI Demonstration & Live Walkthrough Guide

Step-by-step instructions for demonstrating the **Cerberus AI Platform** live in control rooms or conducting simulated verification runs.

---

## 1. Quick Fullstack Startup

Run the automated launcher:
```cmd
start_fullstack.bat
```
- **FastAPI Core Backend:** `http://localhost:8000`
- **React Executive Control Room:** `http://localhost:5173`

---

## 2. Interactive Page Walkthrough

1. **Executive Overview (`/`):** View fleet-wide safety compliance, active violations, real-time FPS throughput, and 7-day historical incident curves.
2. **Multi-Camera Live Wall (`/live`):** Observe real-time bounding box annotations, persistent `Worker-ID` tracking badges, and focus stream zoom.
3. **Incident Triage Inbox (`/violations`):** Triage incoming safety alerts across Unacknowledged, Accepted, and Disputed categories.
4. **Worker Compliance & Proof Gallery (`/compliance`):** Inspect individual worker scorecards, view visual evidence thumbnails in the timeline, zoom in on high-res snapshots, and perform selective multi-item violation deletion.
5. **Zone PPE Rules Manager (`/zones`):** Customize PPE requirements per zone and adjust temporal noise debounce thresholds ($\ge 8/10$ window).
6. **Camera Stream Manager (`/cameras`):** Register RTSP streams, USB webcams, or MP4 video files with automatic health checks.
7. **Model Telemetry & Hardware Intelligence (`/model`):** Monitor live CPU load, system RAM usage, GPU VRAM allocation, and estimate extra webcam capacity headroom.

---

## 3. CLI Testing & Sandbox Inference

To verify model inference directly on an uploaded image or video clip from the terminal:
```bash
python src/core/detector.py 0 "General Plant Floor"
```
