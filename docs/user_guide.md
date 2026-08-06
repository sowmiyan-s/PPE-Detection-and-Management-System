# EdgeVision PPE Compliance Platform – User Guide

## Overview

The EdgeVision PPE Compliance Platform monitors workers in industrial
environments using AI-powered computer vision to detect Personal Protective
Equipment (PPE) compliance in real time.

### What the system detects

| Item | What is checked |
|------|----------------|
| Safety helmet | Present, absent, or incorrectly worn |
| Reflective safety vest | Present or absent |
| Safety boots | Present or absent |
| Safety harness / belt | Present or absent |
| Lanyard | Connected or disconnected |
| Safety hook | Present and connected appropriately |
| Worker | Identified and tracked across frames |

---

## Getting Started

### Starting the Streamlit dashboard

```bash
streamlit run app.py
```

Open your browser at `http://localhost:8501` (or the Replit preview URL).

### Starting the live WebSocket server

```bash
python server.py
```

Open your browser at `http://localhost:8000`.

---

## Dashboard Pages

### 📷 Live Monitoring

1. Select the **camera source** (webcam index, RTSP URL, or video file).
2. Select the **active zone** (determines which PPE is required).
3. Check **▶ Start detection** to begin the live feed.
4. Worker cards appear below the feed showing compliance status:
   - **Green border** — worker is compliant.
   - **Red border** — worker has a violation; missing PPE is listed in red.
5. Uncheck **Start detection** to pause.

### 🚨 Active Violations

Shows the 50 most recent violations received via MQTT.

- Each card shows: worker ID, zone, timestamp, missing PPE, detected PPE, and confidence.
- Click **Clear violations** to reset the list.

### 📋 Event History

Full searchable log (up to 500 events per session).

- Use the **search bar** to filter by worker ID, zone, or missing PPE name.
- Use the **zone filter** to narrow by zone.
- Expand any event row to see the full JSON payload.

### 👷 Worker Compliance

Per-worker statistics showing total violations and last-seen timestamp.

### 🗺️ Zone Configuration

Configure which PPE items are required in each zone.

1. Expand a zone to see and update its required PPE list.
2. Click **Save** to apply changes.
3. Use the **Add new zone** section to create custom zones.

> Changes are applied to the in-memory rule engine immediately but are
> not persisted to the database in this version.

### 📹 Camera Management

Add and view camera sources.

1. Enter a camera name and source (device index or RTSP URL).
2. Click **Add camera** to register it.

### 📊 Reports

Safety summary reports:

- Metric counts for today, this week, and this month.
- Bar chart of violations broken down by **missing PPE class**.
- Bar chart of violations by **zone**.
- **Top offenders** list (workers with the most violations).

### 🤖 Model Monitoring

Displays the active model version, average FPS, mAP50, and real-time FPS history.

---

## Understanding Alerts

An alert is only published after all three conditions are met (Stage-5 temporal
validation):

1. **Frame frequency:** The same violation appears in ≥ 8 of the last 10 frames.
2. **Confidence:** Detection confidence is ≥ 0.30.
3. **Zone dwell time:** The worker has been in the zone for ≥ 2 seconds.

This prevents false alerts from motion blur, partial occlusion, or a worker
briefly passing through a zone.

Once an alert fires for a violation, it is **suppressed** until the worker becomes
compliant — preventing repeated alerts for the same ongoing event.

---

## Safety Zones

| Zone | Required PPE |
|------|-------------|
| General plant | Helmet, vest |
| Construction | Helmet, vest, boots |
| Work at height | Helmet, vest, boots, safety belt, hook |
| Restricted machinery | Helmet, vest |

Zones are configurable via the **Zone Configuration** page or via `config.py`.

---

## Troubleshooting

| Problem | Possible cause | Solution |
|---------|---------------|----------|
| Black/blank camera feed | Camera index wrong | Try source `1` or enter RTSP URL |
| No detections | Model not loaded | Check `MODEL_PATH`; run `train_model.py` |
| MQTT not connected | Broker unreachable | Set `MQTT_BROKER` env var; check firewall |
| Very low FPS | CPU inference | Use a GPU machine or export TensorRT engine |
| Many false alerts | Confidence too low | Increase `DETECTION_CONF` to 0.35–0.50 |
| No alerts despite violations | Temporal threshold not met | Reduce `TEMPORAL_MIN_HITS` in `config.py` |

---

## Environment Variables Quick Reference

See `docs/api_documentation.md` for the full list of configurable environment
variables.

```bash
# Example: private MQTT broker
export MQTT_BROKER=my.broker.com
export MQTT_PORT=8883
export MQTT_USE_TLS=true
export MQTT_USERNAME=ppe
export MQTT_PASSWORD=secret

streamlit run app.py
```
