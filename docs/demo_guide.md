# 🎬 Cerberus AI — Demonstration & Live Walkthrough Guide

> **Repository:** [https://github.com/Vidhyasree14/Cerberus-AI](https://github.com/Vidhyasree14/Cerberus-AI) | **Developer:** Vidhyashree M

Step-by-step instructions for demonstrating the **Cerberus AI Platform** live in control rooms, during technical evaluations, or conducting simulated verification runs.

---

## 1. Quick Fullstack Startup

### Windows (One-Click)
```cmd
start_fullstack.bat
```

### Manual Startup
```bash
# Terminal 1 — FastAPI Backend
python -m src.api.server

# Terminal 2 — React Frontend
cd frontend && npm run dev
```

| Service | URL | Purpose |
| :--- | :--- | :--- |
| **FastAPI Backend** | `http://localhost:8000` | REST API + WebSocket telemetry |
| **Interactive API Docs** | `http://localhost:8000/docs` | Swagger UI for live endpoint testing |
| **React Control Room** | `http://localhost:5173` | Executive dashboard UI |

---

## 2. Demo Checklist — Recommended Walkthrough Order

### ✅ Pre-Demo Setup

Before the live demonstration:

1. Verify at least **one camera** is registered (USB webcam `0` or an MP4 file source).
2. Confirm `models/best.pt` or `models/best.engine` exists in the `models/` directory.
3. Open `http://localhost:5173` in a Chrome/Edge browser in fullscreen mode.
4. Set the active safety zone to **"General Plant Floor"** for the cleanest PPE demo.

---

### 🖥️ Page 1 — Executive Overview (`/`)

**What to demonstrate:**
- Fleet-wide daily compliance rate gauge (target: > 85%).
- Active unacknowledged violation counter.
- 7-day historical incident trend graph (Recharts).
- Real-time FPS throughput across the camera fleet.
- Per-camera health status badges.

**Talking points:**
> *"This executive dashboard gives safety managers an instant overview of site-wide compliance without needing to monitor individual camera feeds."*

---

### 📹 Page 2 — Multi-Camera Live Wall (`/live`)

**What to demonstrate:**
1. Real-time bounding box overlays on each camera feed.
2. Persistent `Worker-ID` tracking badges (`Worker-101`, `Worker-102`, etc.).
3. **Color coding:** Green border = compliant, Red border = violation.
4. Click any camera tile to enter **Focus Stream Mode** — full-resolution, maximum-FPS inspection view.
5. Point out temporal debounce in action — single-frame non-compliance does not trigger alerts.

**Talking points:**
> *"Workers are tracked with persistent IDs across frames, even through temporary occlusions — the system never loses track of who is who."*

---

### 🚨 Page 3 — Incident Triage Inbox (`/violations`)

**What to demonstrate:**
1. The list of unacknowledged safety alerts with evidence snapshots.
2. Click a snapshot thumbnail to open the **full-resolution evidence modal** — detected PPE (green tags) vs. missing PPE (red tags).
3. **Accept** a violation — it moves to the Accepted tab and contributes to compliance records.
4. **Decline** a false positive — evidence is deleted.
5. Use **checkbox multi-select** and **Bulk Delete** for batch operations.
6. Demonstrate filter controls: by camera, date range, worker ID, status.

**Talking points:**
> *"Safety officers can review, accept, or dispute every alert with photographic evidence — creating a complete, auditable compliance trail."*

---

### 👷 Page 4 — Worker Compliance & Proof Gallery (`/compliance`)

**What to demonstrate:**
1. Individual worker scorecards — compliance rate, tracked hours, violation count.
2. **Visual evidence timeline** — click any thumbnail to open high-resolution snapshot modal.
3. **Selective purging** — checkbox individual violations and click "Delete Selected" while watching the compliance score automatically recalculate.
4. **Worker reset** — demonstrate clearing all violations for a worker.

**Talking points:**
> *"Each worker has a complete, timestamped photographic compliance record. Violations can be selectively removed if disputed, with automatic score recalculation."*

---

### ⚙️ Page 5 — Zone PPE Rules Manager (`/zones`)

**What to demonstrate:**
1. The configured safety zones and their PPE requirement lists.
2. Add a new PPE requirement to a zone and observe the system immediately begin enforcing it.
3. Adjust the **temporal threshold** (frame window / dwell time) and explain the false-alarm tradeoff.

**Talking points:**
> *"Every operational area has its own configurable PPE ruleset. The system enforces different requirements for a welding station versus a general plant floor — all in real time."*

---

### 📡 Page 6 — Camera Stream Manager (`/cameras`)

**What to demonstrate:**
1. Add a new camera source (webcam index `0`, or an RTSP URL if available).
2. Watch the camera health card appear with live FPS and status.
3. Delete a camera — demonstrate clean thread termination.

---

### 📊 Page 7 — Model Telemetry & Capacity Intelligence (`/model`)

**What to demonstrate:**
1. Live CPU utilization, RAM usage, and GPU VRAM allocation gauges.
2. Real-time inference FPS and P95 latency.
3. **Extra webcam capacity estimator** — show how many additional cameras the current hardware can support.
4. The 19-class model statistics panel.

**Talking points:**
> *"The system provides complete transparency into hardware utilization and explicitly tells you how many additional cameras you can add before hitting a performance ceiling."*

---

### 📋 Page 8 — Reports & Audit Export (`/reports`)

**What to demonstrate:**
1. Generate a compliance summary for the last 7 days.
2. Export as **CSV** or **Excel** for regulatory submission.
3. Show the per-zone compliance heatmap and worst-offender rankings.

---

## 3. CLI Testing & Sandbox Inference

Verify model inference directly from the terminal on a webcam or video file:

```bash
# Test inference on default webcam (index 0) in "General Plant Floor" zone
python src/core/detector.py 0 "General Plant Floor"

# Test inference on an MP4 video file
python src/core/detector.py /path/to/site_footage.mp4 "Construction Zone"

# Test inference on an RTSP stream
python src/core/detector.py rtsp://192.168.1.100:554/stream1 "Work at Height"
```

### API Health Check

```bash
# Verify all core API endpoints are responding
curl http://localhost:8000/api/zones
curl http://localhost:8000/api/cameras
curl http://localhost:8000/api/violations
curl http://localhost:8000/api/model/benchmark
```

---

## 4. Common Demo Scenarios

### Scenario A: PPE Violation Demonstration
1. Register a webcam or MP4 with a worker **without a hard hat** visible.
2. Set zone to **"General Plant Floor"** (requires `Hard_hat` + `Vest`).
3. After ~2 seconds of continuous detection, observe the `No-Helmet` violation appear in the inbox.
4. Accept the violation and navigate to `/compliance` to see it in the worker's timeline.

### Scenario B: Multi-Camera Capacity Demo
1. Register 4–8 camera sources (can be the same MP4 file multiple times for demo purposes).
2. Navigate to `/live` to see all camera tiles updating in real time.
3. Open `/model` and show the GPU utilization and extra-camera capacity estimator.

### Scenario C: Temporal Noise Suppression Demo
1. Repeatedly wave a hand in front of the webcam lens to cause brief occlusion.
2. Observe that the bounding boxes flicker but **no spurious violation** appears in the inbox.
3. Explain the ≥ 8/10 frame threshold that prevented the transient false alert.

---

*Part of the [Cerberus AI](https://github.com/Vidhyasree14/Cerberus-AI) platform — developed by Vidhyashree M.*
