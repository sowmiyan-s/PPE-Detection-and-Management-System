# 📡 Cerberus AI — REST & WebSocket API Specification

> **Repository:** [https://github.com/Vidhyasree14/Cerberus-AI](https://github.com/Vidhyasree14/Cerberus-AI) | **Developer:** Vidhyashree M

Cerberus AI exposes a high-throughput RESTful management API and a low-latency WebSocket telemetry stream, both powered by **FastAPI** with async I/O throughout.

---

## 🌐 Interactive OpenAPI Documentation

When the FastAPI backend is running, live interactive schemas are accessible at:

| Interface | URL |
| :--- | :--- |
| **Swagger UI** | `http://localhost:8000/docs` |
| **ReDoc** | `http://localhost:8000/redoc` |
| **OpenAPI JSON** | `http://localhost:8000/openapi.json` |

---

## 📌 REST Endpoints Reference

### 1. Safety Zones (`/api/zones`)

#### `GET /api/zones`
Retrieve all registered safety zones, required PPE items, and temporal thresholds.

**Response Schema:**
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

**Request Body:**
```json
{
  "id": "ZONE-02",
  "name": "Work at Height",
  "required_ppe": ["Hard_hat", "Vest", "Boots", "Fire_prevention_Net"],
  "frame_threshold": 8,
  "dwell_seconds": 2,
  "confidence": 0.65
}
```

#### `DELETE /api/zones/{zone_id}`
Remove a zone configuration by ID.

---

### 2. Camera Stream Management (`/api/cameras`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/cameras` | List all registered camera streams with live FPS, resolution, and status |
| `POST` | `/api/cameras` | Register a new camera stream (webcam index, RTSP URL, HTTP stream, or YouTube Live URL) |
| `DELETE` | `/api/cameras/{cam_id}` | Remove a camera and safely terminate its grabber and pipeline threads |
| `POST` | `/api/stream/focus` | Set the active focus stream for high-FPS rendering |

**POST `/api/cameras` Request Body:**
```json
{
  "source": "rtsp://192.168.1.100:554/stream1",
  "name": "Plant Entrance CAM-01",
  "zone": "General Plant Floor"
}
```

**Camera Status Response:**
```json
{
  "id": "CAM-01",
  "name": "Plant Entrance CAM-01",
  "source": "rtsp://192.168.1.100:554/stream1",
  "status": "running",
  "fps": 24.5,
  "resolution": "640x480",
  "zone": "General Plant Floor",
  "uptime_seconds": 3642
}
```

---

### 3. Safety Violations & Evidence (`/api/violations`)

#### `GET /api/violations`
Query violation records with multi-criteria filtering.

**Query Parameters:**

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `cameras` | `string` | Comma-separated camera IDs to filter |
| `date_range` | `string` | Preset: `today`, `7d`, `30d` |
| `start_date` | `ISO8601` | Custom start datetime |
| `end_date` | `ISO8601` | Custom end datetime |
| `zone_id` | `string` | Filter by zone ID |
| `worker_id` | `string` | Filter by Worker-ID |
| `status` | `string` | `unacknowledged` \| `accepted` \| `declined` |
| `limit` | `integer` | Maximum number of records to return (default: 100) |

**Response Item Schema:**
```json
{
  "id": "EVT-1001",
  "camera_id": "CAM-01",
  "worker_id": "Worker-101",
  "zone": "General Plant Floor",
  "missing_ppe": ["No-Helmet", "No-Vest"],
  "timestamp": "2026-08-20T14:30:00Z",
  "snapshot_url": "/evidence/EVT-1001.jpg",
  "status": "unacknowledged",
  "confidence": 0.91
}
```

#### `POST /api/violations/purge` — Bulk Purge
Purge multiple selected violation IDs in a single transaction:
```json
{
  "ids": ["EVT-1001", "EVT-1002", "EVT-1003"]
}
```

#### `DELETE /api/violations/{evt_id}` — Single Delete
Delete a single violation evidence record and its associated snapshot.

#### `POST /api/violations/{evt_id}/reject`
Mark an incident record as disputed or rejected by a safety officer:
```json
{
  "reason": "Worker was in designated safe rest area"
}
```

---

### 4. Worker Compliance (`/api/workers`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/workers` | Retrieve per-worker compliance scorecards, tracking hours, and violation tallies |
| `DELETE` | `/api/workers/{worker_id}` | Delete a worker profile and all associated history |
| `DELETE` | `/api/workers/{worker_id}/violations` | Purge all violations for a worker, resetting their compliance to 100% |

**Worker Scorecard Response:**
```json
{
  "id": "Worker-101",
  "total_tracked_hours": 42.5,
  "total_violations": 3,
  "compliance_rate": 96.8,
  "last_seen": "2026-08-20T17:55:00Z",
  "zone": "General Plant Floor",
  "violations": [
    {
      "id": "EVT-1001",
      "missing": ["No-Helmet"],
      "timestamp": "2026-08-20T14:30:00Z",
      "status": "accepted"
    }
  ]
}
```

---

### 5. Hardware & Telemetry (`/api/model/benchmark`)

#### `GET /api/model/benchmark`
Returns real-time model benchmarks, live hardware telemetry (CPU, RAM, GPU, Jetson SoC), and webcam capacity estimation.

**Full Response Schema:**
```json
{
  "model_name": "Cerberus AI YOLOv8 PPE Detector",
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
    "host_os": "Ubuntu 22.04 / Windows 11",
    "device_type": "Dedicated GPU (NVIDIA GeForce GTX 1650)",
    "is_jetson": false,
    "cpu": {
      "physical_cores": 4,
      "logical_cores": 8,
      "utilization_percent": 68.2
    },
    "ram": {
      "total_gb": 15.86,
      "used_gb": 11.2,
      "utilization_percent": 70.6
    },
    "gpu": {
      "device_name": "NVIDIA GeForce GTX 1650",
      "vram_total_mb": 4096,
      "vram_used_mb": 512,
      "utilization_percent": 45.0
    }
  },
  "stream_capacity": {
    "recommended_extra_webcams": 11,
    "recommended_max_streams": 12,
    "capacity_presets": {
      "balanced": { "max_supported_streams": 12, "extra_webcams_available": 11 },
      "high_density": { "max_supported_streams": 16, "extra_webcams_available": 15 },
      "high_speed": { "max_supported_streams": 8, "extra_webcams_available": 7 }
    }
  }
}
```

---

### 6. Reports & Audit Export (`/api/reports`)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/reports/summary` | Aggregate compliance statistics for a given date range |
| `GET` | `/api/reports/export/csv` | Export violation records as CSV |
| `GET` | `/api/reports/export/excel` | Export full compliance audit as Excel workbook |

---

## ⚡ WebSocket Telemetry Protocol (`WS /ws`)

Connect to the live telemetry stream to receive real-time JSON frames at ~30 Hz:

```
ws://localhost:8000/ws
```

### Telemetry Frame Schema

```json
{
  "type": "telemetry",
  "camera_id": "CAM-01",
  "camera_name": "Plant Entrance",
  "timestamp": "2026-08-20T19:30:00.123Z",
  "fps": 24.5,
  "zone": "General Plant Floor",
  "workers": [
    {
      "id": "Worker-101",
      "bbox": [140, 95, 320, 510],
      "zone": "General Plant Floor",
      "detected": ["Hard_hat", "Vest"],
      "missing": [],
      "compliant": true,
      "confidence": 0.94,
      "track_age_frames": 240
    },
    {
      "id": "Worker-102",
      "bbox": [400, 110, 580, 490],
      "zone": "General Plant Floor",
      "detected": ["Vest"],
      "missing": ["Hard_hat"],
      "compliant": false,
      "confidence": 0.87,
      "track_age_frames": 64
    }
  ],
  "frame_stats": {
    "total_workers": 2,
    "compliant_workers": 1,
    "violation_workers": 1,
    "compliance_rate": 50.0
  }
}
```

### Client-Side WebSocket Example (JavaScript)

```js
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (event) => {
  const frame = JSON.parse(event.data);
  if (frame.type === 'telemetry') {
    console.log(`Camera: ${frame.camera_id} | FPS: ${frame.fps}`);
    frame.workers.forEach(worker => {
      console.log(`  ${worker.id}: ${worker.compliant ? '✅ Compliant' : '🚨 VIOLATION'}`);
    });
  }
};
```

---

## 🔐 Error Responses

All endpoints return standardized error responses:

```json
{
  "detail": "Camera CAM-99 not found.",
  "status_code": 404
}
```

| HTTP Code | Meaning |
| :---: | :--- |
| `200` | Success |
| `201` | Created |
| `400` | Bad Request — invalid parameters |
| `404` | Not Found — resource does not exist |
| `422` | Unprocessable Entity — validation error |
| `500` | Internal Server Error |

---

*Part of the [Cerberus AI](https://github.com/Vidhyasree14/Cerberus-AI) platform — developed by Vidhyashree M.*
