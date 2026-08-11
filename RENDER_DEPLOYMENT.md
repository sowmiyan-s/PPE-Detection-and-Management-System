# 🚀 EdgeVision — Render Cloud Deployment Guide

This guide provides step-by-step instructions to deploy both the **FastAPI Python Backend** and **React Dashboard Frontend** of EdgeVision to [Render](https://render.com).

---

## 📋 Prerequisites

1. A **GitHub** account containing your EdgeVision repository.
2. A free **Render** account at [render.com](https://render.com).
3. A free **MongoDB Atlas** database cluster (or connection string).

---

## ⚡ Option 1: 1-Click Render Blueprint Deployment (Recommended)

Render Blueprints automatically read `render.yaml` from your repo and configure everything.

### Steps:
1. Push your EdgeVision repository to **GitHub**.
2. Log into [Render Dashboard](https://dashboard.render.com).
3. Click **New +** > **Blueprint**.
4. Connect your GitHub repository.
5. Render will automatically detect `render.yaml` and offer the services:
   - **`edgevision-fullstack`** (Recommended: Single Web Service running both Frontend and Backend on 1 free Render instance).
6. Fill in your environment variables:
   - `MONGODB_URI`: Your MongoDB Atlas URI (e.g., `mongodb+srv://user:pass@cluster.mongodb.net/?appName=Cluster0`).
7. Click **Apply**.
8. Render will build the container and deploy your live app at `https://<your-app-name>.onrender.com`.

---

## 🛠️ Option 2: Manual Web Service Deployment on Render

If you prefer setting up a single Docker Web Service manually on Render:

### Steps:

1. Go to [Render Dashboard](https://dashboard.render.com).
2. Click **New +** > **Web Service**.
3. Select **Build and deploy from a Git repository** and choose your repo.
4. Set the following settings:
   - **Name**: `edgevision`
   - **Language**: `Docker`
   - **Dockerfile Path**: `./Dockerfile`
   - **Instance Type**: `Free` (or `Starter`)
5. Under **Environment Variables**, add:
   | Key | Value | Description |
   | :--- | :--- | :--- |
   | `MONGODB_URI` | `mongodb+srv://...` | MongoDB Atlas database URI |
   | `MONGODB_DB_NAME` | `edgevision` | Database name |
   | `PERFORMANCE_PROFILE` | `low_end` | Optimizes inference for CPU/cloud instances |
   | `DETECTION_CONF` | `0.20` | YOLO detection confidence threshold |
6. Click **Create Web Service**.

---

## 🍃 Setting up MongoDB Atlas (Free Cloud Database)

Since local disk on Render free tier is ephemeral (resets on restart), using **MongoDB Atlas** ensures all camera configs, zone rules, and violation incidents persist permanently:

1. Sign up at [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
2. Create a **Free M0 Cluster**.
3. Under **Database Access**, create a user with read/write access.
4. Under **Network Access**, add IP `0.0.0.0/0` (Allow Access from Anywhere).
5. Click **Connect** > **Drivers** and copy your connection string:
   ```text
   mongodb+srv://<username>:<password>@cluster0.mongodb.net/?retryWrites=true&w=majority
   ```
6. Set this as `MONGODB_URI` in Render environment variables.

---

## 📹 YouTube Live Links & RTSP Stream Monitoring in Cloud

When running on Render:
- **Hardware Webcams (Index 0)** will automatically fall back to EdgeVision's simulated live camera stream with timestamp telemetry (since cloud servers do not have physical USB webcams attached).
- **RTSP Streams, Video URLs, and YouTube Live Links** work fully on-the-fly!
- To monitor a YouTube live stream:
  1. Open the deployed dashboard at `https://your-app.onrender.com/cameras`.
  2. Click **+ Register new camera / stream**.
  3. Paste any YouTube Live stream or video URL (e.g. `https://www.youtube.com/watch?v=...`).
  4. Select safety zone and save.

---

## 🔍 Verification & Diagnostics

Once deployed, test your deployment:

- **Dashboard**: `https://<your-app-name>.onrender.com`
- **Health Check Endpoint**: `https://<your-app-name>.onrender.com/health`
- **API Endpoints**: `https://<your-app-name>.onrender.com/api/cameras`
- **Live MJPEG Stream**: `https://<your-app-name>.onrender.com/stream?camera_id=CAM-01`
- **WebSockets**: Automatically connects via `wss://<your-app-name>.onrender.com/ws`

---

## 🔄 Local Development Workflow (Unchanged)

Deploying to Render does **NOT** alter your local setup:
- Run locally on Windows: `start_fullstack.bat`
- Run local Docker: `docker-compose up`
- Run local dev backend: `python -m src.api.server`
- Run local dev frontend: `cd frontend && npm run dev`
