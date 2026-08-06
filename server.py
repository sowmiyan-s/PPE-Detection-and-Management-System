"""
FastAPI WebSocket live-streaming server.

Endpoints
---------
GET  /          — HTML dashboard (Live Monitoring)
GET  /health    — JSON health check
GET  /zones     — list available safety zones
POST /zones     — update active zone
WS   /ws        — streams annotated frames + worker states as JSON
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import time
from contextlib import asynccontextmanager

import cv2
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

import config
from vision_pipeline import VisionPipeline

log = logging.getLogger(__name__)

# ── Global state ───────────────────────────────────────────────────────────────

pipeline: VisionPipeline | None = None
camera:   cv2.VideoCapture | None = None
_active_zone = config.DEFAULT_ZONE
_fps_stats: dict = {"fps": 0.0, "frame_count": 0, "start_time": time.time()}


# ── WebSocket connection manager ───────────────────────────────────────────────

class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)
        log.info("WS connected – total: %d", len(self.active))

    def disconnect(self, ws: WebSocket) -> None:
        self.active = [c for c in self.active if c is not ws]
        log.info("WS disconnected – total: %d", len(self.active))

    async def broadcast(self, data: str) -> None:
        dead: list[WebSocket] = []
        for ws in list(self.active):
            try:
                await ws.send_text(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline, camera
    camera_index = config.DEFAULT_CAMERA_INDEX

    try:
        pipeline = VisionPipeline(zone=_active_zone)
        camera   = cv2.VideoCapture(camera_index)
        if not camera.isOpened():
            log.warning("Camera %s not available – inference loop will skip capture", camera_index)
        else:
            camera.set(cv2.CAP_PROP_FRAME_WIDTH,  config.FRAME_WIDTH)
            camera.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)

        asyncio.create_task(vision_loop())
        log.info("Vision pipeline started (zone=%s)", _active_zone)
    except Exception as exc:
        log.error("Pipeline init failed: %s", exc)

    yield

    if camera and camera.isOpened():
        camera.release()
    if pipeline:
        pipeline.release()


app = FastAPI(title="EdgeVision PPE Safety Server", lifespan=lifespan)


# ── Vision loop ───────────────────────────────────────────────────────────────

async def vision_loop() -> None:
    global _fps_stats
    frame_interval = 1.0 / config.TARGET_FPS
    _fps_stats["start_time"] = time.time()

    while True:
        loop_start = time.time()

        if camera is None or not camera.isOpened() or pipeline is None:
            await asyncio.sleep(0.5)
            continue

        ok, frame = camera.read()
        if not ok:
            await asyncio.sleep(0.1)
            continue

        # Run inference in thread pool to avoid blocking the event loop
        try:
            annotated, workers = await asyncio.get_event_loop().run_in_executor(
                None, pipeline.process_frame, frame
            )
        except Exception as exc:
            log.error("Inference error: %s", exc)
            await asyncio.sleep(frame_interval)
            continue

        # FPS tracking
        _fps_stats["frame_count"] += 1
        elapsed = time.time() - _fps_stats["start_time"]
        if elapsed > 0:
            _fps_stats["fps"] = round(_fps_stats["frame_count"] / elapsed, 1)

        # Encode frame as JPEG → base64
        ok_enc, buf = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if not ok_enc:
            await asyncio.sleep(frame_interval)
            continue

        payload = json.dumps({
            "frame":   base64.b64encode(buf.tobytes()).decode("ascii"),
            "workers": workers,
            "fps":     _fps_stats["fps"],
            "zone":    _active_zone,
        })

        if manager.active:
            await manager.broadcast(payload)

        # Throttle to target FPS
        elapsed_loop = time.time() - loop_start
        sleep_time = max(0.0, frame_interval - elapsed_loop)
        await asyncio.sleep(sleep_time)


# ── HTML dashboard ────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EdgeVision – Live Safety Dashboard</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', sans-serif; background: #0d1117; color: #e6edf3; }
    header { background: #161b22; padding: 16px 24px; border-bottom: 1px solid #30363d;
             display: flex; align-items: center; gap: 12px; }
    header h1 { font-size: 1.25rem; color: #58a6ff; }
    .badge { background: #238636; color: #fff; padding: 2px 10px; border-radius: 12px;
             font-size: 0.75rem; margin-left: auto; }
    .badge.offline { background: #da3633; }
    .main { display: flex; gap: 16px; padding: 16px; max-width: 1600px; margin: 0 auto; }
    .video-panel { flex: 3; background: #161b22; border-radius: 8px; overflow: hidden;
                   border: 1px solid #30363d; }
    .video-panel img { width: 100%; display: block; }
    .side-panel { flex: 1; display: flex; flex-direction: column; gap: 12px; min-width: 280px; }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 14px; }
    .card h2 { font-size: 0.85rem; color: #8b949e; text-transform: uppercase;
               letter-spacing: .05em; margin-bottom: 10px; }
    .stat-row { display: flex; justify-content: space-between; margin: 4px 0;
                font-size: 0.9rem; }
    .worker-card { background: #21262d; border-radius: 6px; padding: 10px; margin-bottom: 8px;
                   border-left: 4px solid #238636; }
    .worker-card.violation { border-left-color: #da3633; }
    .worker-id { font-weight: 600; font-size: 0.95rem; }
    .ppe-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
    .tag { padding: 2px 8px; border-radius: 10px; font-size: 0.72rem;
           background: #1f6feb33; color: #58a6ff; border: 1px solid #1f6feb88; }
    .tag.missing { background: #da363333; color: #ff7b72; border-color: #da363388; }
    .fps-bar { height: 4px; background: #30363d; border-radius: 2px; margin-top: 6px; }
    .fps-fill { height: 100%; background: #238636; border-radius: 2px; transition: width .5s; }
    #zone-select { background: #21262d; color: #e6edf3; border: 1px solid #30363d;
                   border-radius: 4px; padding: 4px 8px; font-size: 0.85rem; width: 100%; }
    #alerts-list { max-height: 240px; overflow-y: auto; font-size: 0.82rem; }
    .alert-item { padding: 6px 0; border-bottom: 1px solid #21262d; color: #ff7b72; }
    .alert-item time { color: #8b949e; font-size: 0.75rem; }
  </style>
</head>
<body>
<header>
  <span>🏭</span>
  <h1>EdgeVision PPE Safety Dashboard</h1>
  <span id="conn-badge" class="badge offline">Offline</span>
</header>
<div class="main">
  <div class="video-panel">
    <img id="live-feed" src="" alt="Live camera feed">
  </div>
  <div class="side-panel">

    <div class="card">
      <h2>System</h2>
      <div class="stat-row"><span>FPS</span><strong id="fps">—</strong></div>
      <div class="stat-row"><span>Active workers</span><strong id="worker-count">0</strong></div>
      <div class="stat-row"><span>Active zone</span><strong id="zone-label">—</strong></div>
      <div class="fps-bar"><div class="fps-fill" id="fps-fill" style="width:0%"></div></div>
    </div>

    <div class="card">
      <h2>Zone</h2>
      <select id="zone-select" onchange="setZone(this.value)">
        <option value="general_plant">General Plant</option>
        <option value="construction">Construction</option>
        <option value="work_at_height">Work at Height</option>
        <option value="restricted_machinery">Restricted Machinery</option>
      </select>
    </div>

    <div class="card" id="workers-card">
      <h2>Workers</h2>
      <div id="workers-list"><em style="color:#8b949e;font-size:.85rem">No workers detected</em></div>
    </div>

    <div class="card">
      <h2>Recent Violations</h2>
      <div id="alerts-list"></div>
    </div>

  </div>
</div>

<script>
const MAX_ALERTS = 50;
let alerts = [];

const feedEl       = document.getElementById("live-feed");
const fpsEl        = document.getElementById("fps");
const fpsFill      = document.getElementById("fps-fill");
const workerCount  = document.getElementById("worker-count");
const zoneLabel    = document.getElementById("zone-label");
const workersList  = document.getElementById("workers-list");
const alertsList   = document.getElementById("alerts-list");
const connBadge    = document.getElementById("conn-badge");

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws    = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onopen = () => {
    connBadge.textContent = "Live";
    connBadge.className   = "badge";
  };

  ws.onclose = () => {
    connBadge.textContent = "Offline";
    connBadge.className   = "badge offline";
    setTimeout(connect, 3000);
  };

  ws.onmessage = (ev) => {
    const data = JSON.parse(ev.data);
    if (data.frame) feedEl.src = "data:image/jpeg;base64," + data.frame;

    const fps = data.fps ?? 0;
    fpsEl.textContent       = fps.toFixed(1) + " fps";
    fpsFill.style.width     = Math.min(100, fps / 25 * 100) + "%";
    zoneLabel.textContent   = (data.zone ?? "").replace(/_/g, " ");
    workerCount.textContent = (data.workers ?? []).length;

    renderWorkers(data.workers ?? []);
    collectAlerts(data.workers ?? []);
  };
}

function renderWorkers(workers) {
  if (!workers.length) {
    workersList.innerHTML = '<em style="color:#8b949e;font-size:.85rem">No workers detected</em>';
    return;
  }
  workersList.innerHTML = workers.map(w => `
    <div class="worker-card ${w.compliant ? "" : "violation"}">
      <div class="worker-id">${w.worker_id} <span style="font-size:.75rem;color:#8b949e">${(w.confidence*100).toFixed(0)}%</span></div>
      <div class="ppe-tags">
        ${(w.detected_ppe||[]).map(p=>`<span class="tag">${p}</span>`).join("")}
        ${(w.missing_ppe||[]).map(p=>`<span class="tag missing">⚠ ${p}</span>`).join("")}
      </div>
    </div>`).join("");
}

function collectAlerts(workers) {
  const now = new Date().toLocaleTimeString();
  workers.filter(w=>!w.compliant).forEach(w => {
    alerts.unshift({ time: now, msg: `${w.worker_id} missing ${w.missing_ppe.join(", ")}` });
  });
  alerts = alerts.slice(0, MAX_ALERTS);
  alertsList.innerHTML = alerts.map(a =>
    `<div class="alert-item"><time>${a.time}</time> ${a.msg}</div>`
  ).join("") || '<em style="color:#8b949e;font-size:.85rem">No violations</em>';
}

function setZone(zone) {
  fetch("/zones", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({zone})
  });
}

connect();
</script>
</body>
</html>"""


# ── REST Endpoints ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTML


@app.get("/health")
async def health():
    return JSONResponse({
        "status": "ok",
        "fps":    _fps_stats["fps"],
        "zone":   _active_zone,
        "ws_connections": len(manager.active),
    })


@app.get("/zones")
async def list_zones():
    from rule_engine import RuleEngine
    engine = RuleEngine()
    return JSONResponse({"zones": engine.list_zones(), "active": _active_zone})


@app.post("/zones")
async def set_zone(body: dict):
    global _active_zone
    zone = body.get("zone", config.DEFAULT_ZONE)
    _active_zone = zone
    if pipeline:
        pipeline.set_zone(zone)
    return JSONResponse({"active": _active_zone})


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()   # keepalive – client sends nothing meaningful
    except WebSocketDisconnect:
        manager.disconnect(ws)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("server:app", host=config.SERVER_HOST, port=config.SERVER_PORT, reload=False)
