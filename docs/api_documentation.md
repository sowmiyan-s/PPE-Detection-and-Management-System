# 📡 Cerberus AI — REST & WebSocket API Specification

Cerberus AI exposes a high-throughput RESTful management API and low-latency WebSocket telemetry streams.

---

## 🌐 Interactive OpenAPI Documentation

When the FastAPI backend is running, live interactive schemas are accessible at:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

---

## 📌 REST Endpoints Reference

### 1. Safety Zones (`/api/zones`)

#### `GET /api/zones`
Retrieve all registered safety zones, required PPE items, and temporal thresholds.
```json
{
  "zones": ["General Plant Floor", "Construction Area", "Work at Height"],
  "db_zones": [
    {
      "id": "ZONE-01",
      "name": "General Plant Floor",
      "required_ppe": ["Hard_hat", "Vest"],
      "frame_threshold": 8,
      "dwell_seconds": 2,
      "confidence": 0.60
    }
  ],
  "active": "General Plant Floor"
}
```

#### `POST /api/zones`
Create or update a zone configuration.
```json
{
  "id": "ZONE-02",
  "name": "Work at Height",
  "required_ppe": ["Hard_hat", "Vest", "Boots"],
  "frame_threshold": 8,
  "dwell_seconds": 2,
  "confidence": 0.65
}
```

---

### 2. Camera Stream Management (`/api/cameras`)

- `GET /api/cameras` — List all registered camera streams with live FPS, resolution, and status.
- `POST /api/cameras` — Register a new camera stream (Webcam index, RTSP URL, HTTP stream, or YouTube Live URL).
- `DELETE /api/cameras/{cam_id}` — Remove a camera and safely terminate its grabber and pipeline threads.
- `POST /api/stream/focus` — Set active focus stream for high-FPS rendering.

---

### 3. Safety Violations & Evidence (`/api/violations`)

#### `GET /api/violations`
Query violation records with multi-criteria filtering:
- **Query Parameters:** `cameras`, `date_range`, `start_date`, `end_date`, `zone_id`, `worker_id`, `status`, `limit`.

#### `POST /api/violations/purge` / `DELETE /api/violations/purge`
Purge specific selected violation IDs in bulk:
```json
{
  "ids": ["EVT-1001", "EVT-1002"]
}
```

#### `DELETE /api/violations/{evt_id}`
Delete a single violation evidence record.

#### `POST /api/violations/{evt_id}/reject`
Mark an incident record as disputed or rejected by a safety officer.

---

### 4. Worker Compliance (`/api/workers`)

- `GET /api/workers` — Retrieve per-worker compliance scorecards, tracking hours, and violation tallies.
- `DELETE /api/workers/{worker_id}` — Delete a worker profile and associated history.
- `DELETE /api/workers/{worker_id}/violations` — Purge all violations for a specific worker while retaining the worker record at 100% compliance.

---

### 5. Hardware & Telemetry (`/api/model/benchmark`)

#### `GET /api/model/benchmark`
Returns real-time model benchmarks, live hardware telemetry (CPU, RAM, GPU, Jetson SoC), and webcam capacity estimation.
```json
{
  "model_name": "EdgeVision YOLOv8 PPE Detector",
  "model_version": "v1.0-FP16",
  "weights_file": "best.pt",
  "current_fps": 24.5,
  "latency_ms": {
    "preprocess_ms": 2.1,
    "inference_ms": 12.0,
    "postprocess_ms": 4.4,
    "total_ms": 18.5
  },
  "device_performance": {
    "host_os": "Windows 10 / Ubuntu 22.04",
    "device_type": "Dedicated GPU (NVIDIA GeForce GTX 1650)",
    "is_jetson": false,
    "cpu": { "physical_cores": 4, "logical_cores": 8, "utilization_percent": 68.2 },
    "ram": { "total_gb": 15.86, "used_gb": 11.2, "utilization_percent": 70.6 },
    "gpu": { "device_name": "NVIDIA GeForce GTX 1650", "vram_total_mb": 4096, "vram_used_mb": 512 }
  },
  "stream_capacity": {
    "recommended_extra_webcams": 11,
    "recommended_max_streams": 12,
    "capacity_presets": {
      "balanced": { "max_supported_streams": 12, "extra_webcams_available": 11 }
    }
  }
}
```

---

## ⚡ WebSocket Telemetry Protocol (`WS /ws`)

The WebSocket endpoint streams live JSON frames containing worker states and bounding box coordinates:

```json
{
  "type": "telemetry",
  "camera_id": "CAM-01",
  "timestamp": "2026-08-20T19:30:00Z",
  "fps": 24.5,
  "workers": [
    {
      "id": "Worker-101",
      "bbox": [140, 95, 320, 510],
      "zone": "General Plant Floor",
      "detected": ["Hard_hat", "Vest"],
      "missing": [],
      "compliant": true
    }
  ]
}
```
