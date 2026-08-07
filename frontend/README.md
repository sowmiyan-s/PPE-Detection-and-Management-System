# Watchful Eye Safety

EdgeVision — PPE Compliance & Work-at-Height Safety Platform

Full Build Prompt (AI/ML Pipeline + Web Application)

Use this as a single reference prompt for building, extending, or explaining the EdgeVision platform end to end.

1. Business Problem

Industrial organisations need to determine whether workers entering operational or hazardous areas are following required safety practices. The system must detect and reason about:

Safety item Detection requirement Safety helmet Present, absent, or incorrectly worn Reflective safety vest Present or absent Safety boots Present or absent Safety harness/belt Present or absent Lanyard Connected or disconnected Safety hook Present and connected appropriately Worker Person identification and tracking Restricted zone Unauthorised entry Work at height Worker operating above the configured height/platform zone

The core technical challenge is not just detecting PPE objects — it's determining whether detected PPE belongs to the correct person, in the correct zone, under that zone's rules:

Helmet detected → Is it on a tracked worker? → Is that worker in a restricted zone?
→ Does the zone require a helmet/vest/boots/harness? → Generate compliance or violation event


2. AI/ML Pipeline (5 stages)

Person detection & tracking — detect each worker, assign a persistent tracking ID (Worker-101, Worker-102, …) so the same person doesn't re-trigger an alert every frame.

PPE detection — classes: person, helmet, vest, boots, safety_belt, lanyard, hook, anchor_point. Helmet/vest are easier; boots, belts, lanyards, hooks are small, often occluded, or angle-dependent.

Person-to-PPE association — bounding-box containment, body-region mapping, pose estimation, nearest-person association, or tracking-based temporal association. Output example:

Worker-101: Helmet: Yes | Vest: Yes | Boots: Yes | Harness: No | Hook connected: No


Rule engine — required PPE is configurable per zone:

Zone Required PPE General plant area Helmet, vest Construction area Helmet, vest, boots Work-at-height area Helmet, vest, boots, harness, connected hook Restricted machinery area Helmet, vest, authorisation

Temporal validation — suppress false alerts from a single noisy frame:

Alert only if: violation in 8/10 last frames AND confidence > threshold AND worker in zone > 2s


Accuracy improvement focus: small-object detection (higher inference resolution, person-cropping before PPE detection, tiling, small-object augmentation, camera-specific models, secondary detectors for hard classes); difficult conditions (low light, harsh sun, shadows, dust, motion blur, partial visibility, crowding, varied helmet/vest colors, workers facing away/bending/sitting, PPE held not worn); hard negatives (yellow machinery as helmet, reflective material as vest, shoes as boots, loose rope as lanyard, unconnected nearby hooks).

Jetson deployment path:

Trained model → ONNX → TensorRT FP16 engine → TensorRT INT8 experiment → DeepStream/GStreamer app


Engine must be generated on the target Jetson (or identical hardware/software config). Maintain the ONNX model, calibration data, engine-generation command, and exact JetPack/DeepStream versions — not just the .engine file — so it can be rebuilt.

Model evaluation metrics to report: precision & recall per PPE class, mAP50, mAP50–95, violation precision, false alerts/hour, FPS, P95 inference latency, GPU/CPU/memory use, temperature, power mode.

Initial deployment target: single 1080p stream, ≥12 FPS minimum (20+ preferred), FP16 TensorRT, 8+ hours continuous operation, no repeated alert for the same ongoing violation.

3. Web Application — Pages & Features (as built)

Built in React (Vite), styled with Tailwind utility classes, charts via recharts, icons via lucide-react. Industrial control-room visual design: charcoal background, hazard-tape amber accent, safety-orange for violations, safety-green for compliance, condensed industrial display type (Oswald) + monospace (IBM Plex Mono) for IDs/telemetry, with a diagonal hazard-stripe motif as the signature UI element on page headers and violation cards.

Overview (/) — system health status, quick stat cards (cameras online, active violations, daily compliance %, workers tracked), 7-day violation trend chart, violations-by-zone breakdown, live alert ticker.

Live Monitoring (/live) — multi-camera grid with simulated bounding-box/tracking-ID overlays, overlay toggles (boxes, IDs, pose), click-to-focus single-stream modal, per-camera status (online/degraded/offline).

Active Violations (/violations) — unacknowledged event list with worker, zone, camera, violation type, confidence, evidence thumbnail, "view clip" and "acknowledge" actions.

Event History (/events) — searchable/filterable table (by worker, violation type, zone), status badges (open/reviewed), CSV export action.

Worker Compliance (/compliance) — worker list with compliance %, drill-down detail panel with a compliance ring, shift/zone/incident summary, recent incident log.

Zone Configuration (/zones) — per-zone required-PPE toggles (helmet, vest, boots, harness, connected hook, authorisation), temporal validation sliders (frame threshold, minimum dwell time).

Camera Management (/cameras) — camera registry table (resolution, target FPS, latency, status), "register new camera" form.

Reports (/reports) — daily/weekly/monthly toggle, compliance trend line chart, violations-per-zone bar chart, PDF/CSV export buttons.

Model Monitoring (/model) — active model version + precision mode (FP16/INT8), FPS, P95 latency, GPU temp, per-class precision/recall/mAP50 table, live latency chart, power mode & memory use.

Alert record fields modeled: event ID, camera ID, zone ID, worker tracking ID, violation type, detected PPE, missing PPE, confidence, timestamp, image evidence, video clip, acknowledgement status, model version.

Suggested backend tables: cameras, zones, zone_ppe_rules, ppe_types, detection_events, detected_objects, worker_tracks, violation_events, alert_deliveries, event_images, event_videos, model_versions, inference_metrics, users, roles, audit_logs — PostgreSQL for structured data; object/file storage for images and video clips, with locations recorded in the DB.

4. Mandatory Final Submission Checklist

Complete source code

Database creation and migration scripts

API documentation

Model-training code

Dataset structure and labelling guide

ONNX model

TensorRT engine-generation instructions

Jetson installation and startup service

Web application

Test cases

Accuracy report

FPS, latency, memory, and temperature benchmark

User guide

Architecture diagram

Final recorded and live demonstration

This project was built with [Lovable](https://lovable.dev).

**Live app**: https://alert-insight-suite.lovable.app

## Build with Lovable
Continue developing this project in the [Lovable editor](https://lovable.dev/projects/292b5b81-979b-4b21-a813-f83b85c5f33f).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
this is readme file