# 📖 Cerberus AI — Operator Standard Operating Procedure (SOP)

> **Repository:** [https://github.com/Vidhyasree14/Cerberus-AI](https://github.com/Vidhyasree14/Cerberus-AI) | **Developer:** Vidhyashree M

Comprehensive operator manual and safety officer reference for daily control room triage, worker compliance verification, zone rule configuration, and audit reporting.

---

## 🎯 Role-Based Access Overview

| Role | Primary Responsibilities | Key Dashboard Pages |
| :--- | :--- | :--- |
| **Control Room Operator** | Live surveillance, incident triage | `/live`, `/violations` |
| **Safety Officer** | Compliance review, worker scorecard verification | `/compliance`, `/reports` |
| **Zone Manager** | PPE rules configuration, threshold tuning | `/zones`, `/cameras` |
| **IT / System Admin** | Hardware monitoring, camera registration | `/model`, `/cameras` |

---

## 🖥️ Daily Operator Workflow

### Step 1 — Start the System

**Windows (one-click):**
```cmd
start_fullstack.bat
```

**Manual startup:**
```bash
# Terminal 1 — Backend
python -m src.api.server

# Terminal 2 — Frontend
cd frontend && npm run dev
```

Open the control room at **`http://localhost:5173`**.

---

### Step 2 — Executive Dashboard (`/`)

On first load, the Executive Dashboard presents a fleet-wide operational summary:

| Widget | Description |
| :--- | :--- |
| **Daily Compliance Rate** | Aggregate percentage of compliant worker appearances |
| **Active Violation Count** | Total unacknowledged safety alerts across all cameras |
| **Live FPS Throughput** | Real-time frames-per-second across the camera fleet |
| **7-Day Incident Trend** | Recharts line graph showing violation frequency over the past week |
| **Camera Fleet Status** | Per-camera online/offline health badges |

> 💡 **Tip:** Use the Executive Dashboard to identify compliance trend degradation before your safety shift briefing.

---

### Step 3 — Live Surveillance & Stream Focus (`/live`)

- The **multi-camera grid** provides fleet-wide situational awareness with live bounding box overlays and `Worker-ID` tracking badges.
- **Focus Stream Mode:** Click any stream tile to expand it to full-resolution, high-frame-rate focus view for close behavioral inspection.
- Each worker bounding box is color-coded:
  - 🟢 **Green border** — Fully compliant worker
  - 🔴 **Red border** — PPE violation detected
- The **zone selector** at the top allows you to switch which safety zone's rules are actively evaluated.

---

### Step 4 — Incident Verification & Triage (`/violations`)

Every detected safety violation enters the incident inbox for operator review:

#### Triage Workflow

```
Violation Candidate Detected
         │
         ▼
  Review Evidence Snapshot
         │
    ┌────┴────┐
    │         │
 ACCEPT     DECLINE
    │         │
    ▼         ▼
Logged as   Deleted as
True Alarm  False Positive
```

| Action | Button | Effect |
| :--- | :--- | :--- |
| **Accept** | ✅ Accept | Validates as true incident; logged to compliance records |
| **Decline** | ❌ Decline | Marks as false positive; evidence deleted from system |
| **Bulk Purge** | 🗑️ Delete Selected | Remove multiple checked violations in a single operation |

#### Filtering Options
- Filter by **camera**, **date range**, **zone**, **worker ID**, and **status** (`Unacknowledged` / `Accepted` / `Declined`).

---

### Step 5 — Worker Compliance Scorecards & Proof Gallery (`/compliance`)

Review individual personnel safety records and manage historical evidence:

- **Compliance Scorecard:** Shows each worker's compliance rate %, total tracked hours, and violation tally.
- **Visual Evidence Gallery:** Click any timeline thumbnail to open the high-resolution snapshot modal displaying:
  - Detected PPE items (green tags)
  - Missing PPE items (red alert tags)
  - Timestamp and camera source
- **Selective Violation Purging:** Use checkboxes to select specific erroneous alerts and click **"Delete Selected"** to remove them while automatically recalculating the worker's compliance score.
- **Worker Reset:** Use **"Clear All Violations"** to reset a worker's compliance history to 100% — useful when a worker ID is reassigned or after equipment errors.

---

### Step 6 — Safety Zone Policy Enforcement (`/zones`)

Configure PPE requirements per operational area:

#### Default Zone Presets

| Zone | Required PPE | Risk Level |
| :--- | :--- | :--- |
| **General Plant Floor** | Hard hat, Reflective vest | 🟡 Medium |
| **Construction Zone** | Hard hat, Vest, Boots, Safety glasses | 🟠 High |
| **Work at Height** | Hard hat, Vest, Boots, Safety net | 🔴 Critical |
| **Machinery Floor** | Hard hat, Vest, Ear protection, Safety glasses | 🟠 High |
| **Welding Area** | Hard hat, Vest, Gloves, Mask, Safety glasses | 🔴 Critical |

#### Temporal Threshold Configuration

| Parameter | Default | Description |
| :--- | :---: | :--- |
| **Frame Threshold** | `8 / 10` | Minimum consecutive frames detecting a violation before triggering an alert |
| **Dwell Seconds** | `2.0 s` | Minimum time a violation must persist before being formally logged |
| **Confidence Threshold** | `0.60` | Minimum YOLO detection confidence to consider a class detected |

> **Increasing** the frame threshold reduces false alarms but may slow response to genuine violations.
> **Decreasing** the dwell time makes the system more sensitive to transient violations.

---

### Step 7 — Camera Stream Manager (`/cameras`)

Register and monitor all video input sources:

| Source Type | Example Input |
| :--- | :--- |
| **USB Webcam** | `0`, `1`, `2` (device index) |
| **IP / RTSP Camera** | `rtsp://192.168.1.100:554/stream1` |
| **HTTP MJPEG Stream** | `http://192.168.1.101:8080/video` |
| **Local MP4 File** | `C:/recordings/site_footage.mp4` |
| **YouTube Live** | `https://www.youtube.com/watch?v=LIVE_ID` |

Each camera card displays live FPS, resolution, assigned zone, and online/offline status.

---

### Step 8 — Reports & Compliance Audit (`/reports`)

Generate regulatory-grade compliance audit reports:

- **Date Range Selection:** Filter compliance data by day, week, month, or custom range.
- **Export Formats:**
  - 📄 **CSV Export** — Raw violation data for custom analysis
  - 📊 **Excel Export** — Formatted audit workbook with per-camera and per-worker breakdowns
- **Charts Included:** 7-day violation trend, per-zone compliance heatmap, worst-offender rankings.

---

### Step 9 — Hardware Telemetry & Capacity (`/model`)

Monitor system health and estimate available camera capacity:

| Metric | Description |
| :--- | :--- |
| **CPU Utilization** | Real-time per-core load percentage |
| **System RAM** | Total / Used / Available with utilization gauge |
| **GPU VRAM** | Allocated vs total VRAM for the inference device |
| **Live Inference FPS** | Current AI model throughput |
| **P95 Latency** | End-to-end pipeline latency at the 95th percentile |
| **Extra Camera Headroom** | Estimated additional webcams supportable at current load |

---

## 🚨 Escalation Procedures

| Severity | Trigger | Operator Action |
| :--- | :--- | :--- |
| **Critical** | Worker missing hard hat in Work at Height zone | Immediately radio safety officer, accept violation |
| **High** | Worker missing vest in Construction Zone | Log violation, schedule safety briefing |
| **Medium** | Worker missing gloves in Machinery Floor | Accept violation, monitor worker |
| **Low** | Transient detection, below dwell threshold | System auto-suppresses — no action needed |

---

*Part of the [Cerberus AI](https://github.com/Vidhyasree14/Cerberus-AI) platform — developed by Vidhyashree M.*
