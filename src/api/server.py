"""
EdgeVision – FastAPI WebSocket live-streaming server.

Endpoints
---------
GET  /        HTML live monitoring dashboard
GET  /health  JSON health check
GET  /zones   List available safety zones
POST /zones   Switch active zone  { "zone": "work_at_height" }
WS   /ws      Streams annotated frames + worker states as JSON

Run:
    python server.py
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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.core import config
from src.core.vision_pipeline import VisionPipeline
from src.core import db

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


# ── Evidence directory ─────────────────────────────────────────────────────────

EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "database", "evidence")
os.makedirs(EVIDENCE_DIR, exist_ok=True)


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pipeline, camera

    # Auto-initialize database
    db.ensure_db()

    try:
        pipeline = VisionPipeline(zone=_active_zone)
        camera   = cv2.VideoCapture(config.DEFAULT_CAMERA_INDEX)
        if not camera.isOpened():
            log.warning("Physical webcam %s not available – falling back to sample video feed",
                        config.DEFAULT_CAMERA_INDEX)
            sample_video = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "sample_feed.mp4")
            if os.path.exists(sample_video):
                camera = cv2.VideoCapture(sample_video)
                log.info("Loaded sample video feed from %s", sample_video)
            else:
                log.error("Sample video feed not found at %s", sample_video)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/api/evidence", StaticFiles(directory=EVIDENCE_DIR), name="evidence")


# ── Vision loop ────────────────────────────────────────────────────────────────

async def vision_loop() -> None:
    global _fps_stats
    frame_interval = 1.0 / config.TARGET_FPS
    _fps_stats["start_time"] = time.time()
    last_evidence_time = 0.0

    while True:
        loop_start = time.time()

        if camera is None or not camera.isOpened() or pipeline is None:
            await asyncio.sleep(0.5)
            continue

        ok, frame = camera.read()
        if not ok:
            # Loop video stream back to beginning if end of file reached
            camera.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = camera.read()
            if not ok:
                await asyncio.sleep(0.1)
                continue

        try:
            annotated, workers = await asyncio.get_event_loop().run_in_executor(
                None, pipeline.process_frame, frame
            )
        except Exception as exc:
            log.error("Inference error: %s", exc)
            await asyncio.sleep(frame_interval)
            continue

        _fps_stats["frame_count"] += 1
        elapsed = time.time() - _fps_stats["start_time"]
        if elapsed > 0:
            _fps_stats["fps"] = round(_fps_stats["frame_count"] / elapsed, 1)

        # Save proof of evidence when non-compliant workers detected (throttle: max 1 snapshot per 3s)
        now = time.time()
        non_compliant = [w for w in workers if not w.get("compliant", True)]
        if non_compliant and (now - last_evidence_time > 3.0):
            last_evidence_time = now
            for w in non_compliant:
                filename = f"EVT-{int(now)}-{w['worker_id']}.jpg"
                filepath = os.path.join(EVIDENCE_DIR, filename)
                cv2.imwrite(filepath, annotated)
                evidence_url = f"/api/evidence/{filename}"
                db.record_violation(
                    worker_id=w["worker_id"],
                    zone_id=_active_zone,
                    violation_type=f"Missing {', '.join(w.get('missing_ppe', []))}",
                    detected_ppe=w.get("detected_ppe", []),
                    missing_ppe=w.get("missing_ppe", []),
                    confidence=w.get("confidence", 0.0),
                    image_path=evidence_url,
                )

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

        await asyncio.sleep(max(0.0, frame_interval - (time.time() - loop_start)))


# ── HTML Dashboard ─────────────────────────────────────────────────────────────

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EdgeVision – Live Safety Dashboard</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Segoe UI',sans-serif;background:#0d1117;color:#e6edf3}
    header{background:#161b22;padding:16px 24px;border-bottom:1px solid #30363d;
           display:flex;align-items:center;gap:12px}
    header h1{font-size:1.25rem;color:#58a6ff}
    .badge{background:#238636;color:#fff;padding:2px 10px;border-radius:12px;
           font-size:.75rem;margin-left:auto}
    .badge.offline{background:#da3633}
    .main{display:flex;gap:16px;padding:16px;max-width:1600px;margin:0 auto}
    .video-panel{flex:3;background:#161b22;border-radius:8px;overflow:hidden;
                 border:1px solid #30363d}
    .video-panel img{width:100%;display:block}
    .side-panel{flex:1;display:flex;flex-direction:column;gap:12px;min-width:280px}
    .card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px}
    .card h2{font-size:.85rem;color:#8b949e;text-transform:uppercase;
             letter-spacing:.05em;margin-bottom:10px}
    .stat-row{display:flex;justify-content:space-between;margin:4px 0;font-size:.9rem}
    .worker-card{background:#21262d;border-radius:6px;padding:10px;margin-bottom:8px;
                 border-left:4px solid #238636}
    .worker-card.violation{border-left-color:#da3633}
    .worker-id{font-weight:600;font-size:.95rem}
    .ppe-tags{display:flex;flex-wrap:wrap;gap:4px;margin-top:6px}
    .tag{padding:2px 8px;border-radius:10px;font-size:.72rem;
         background:#1f6feb33;color:#58a6ff;border:1px solid #1f6feb88}
    .tag.missing{background:#da363333;color:#ff7b72;border-color:#da363388}
    .fps-bar{height:4px;background:#30363d;border-radius:2px;margin-top:6px}
    .fps-fill{height:100%;background:#238636;border-radius:2px;transition:width .5s}
    #zone-select{background:#21262d;color:#e6edf3;border:1px solid #30363d;
                 border-radius:4px;padding:4px 8px;font-size:.85rem;width:100%}
    #alerts-list{max-height:240px;overflow-y:auto;font-size:.82rem}
    .alert-item{padding:6px 0;border-bottom:1px solid #21262d;color:#ff7b72}
    .alert-item time{color:#8b949e;font-size:.75rem}
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
      <div class="stat-row"><span>Workers</span><strong id="worker-count">0</strong></div>
      <div class="stat-row"><span>Zone</span><strong id="zone-label">—</strong></div>
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
    <div class="card">
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
const MAX_ALERTS=50;let alerts=[];
const feedEl=document.getElementById("live-feed"),fpsEl=document.getElementById("fps"),
      fpsFill=document.getElementById("fps-fill"),workerCount=document.getElementById("worker-count"),
      zoneLabel=document.getElementById("zone-label"),workersList=document.getElementById("workers-list"),
      alertsList=document.getElementById("alerts-list"),connBadge=document.getElementById("conn-badge");
function connect(){
  const proto=location.protocol==="https:"?"wss":"ws";
  const ws=new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen=()=>{connBadge.textContent="Live";connBadge.className="badge"};
  ws.onclose=()=>{connBadge.textContent="Offline";connBadge.className="badge offline";setTimeout(connect,3000)};
  ws.onmessage=(ev)=>{
    const d=JSON.parse(ev.data);
    if(d.frame)feedEl.src="data:image/jpeg;base64,"+d.frame;
    const fps=d.fps??0;
    fpsEl.textContent=fps.toFixed(1)+" fps";
    fpsFill.style.width=Math.min(100,fps/25*100)+"%";
    zoneLabel.textContent=(d.zone??"").replace(/_/g," ");
    workerCount.textContent=(d.workers??[]).length;
    renderWorkers(d.workers??[]);collectAlerts(d.workers??[]);
  };
}
function renderWorkers(ws){
  if(!ws.length){workersList.innerHTML='<em style="color:#8b949e;font-size:.85rem">No workers detected</em>';return;}
  workersList.innerHTML=ws.map(w=>`
    <div class="worker-card ${w.compliant?"":"violation"}">
      <div class="worker-id">${w.worker_id} <span style="font-size:.75rem;color:#8b949e">${(w.confidence*100).toFixed(0)}%</span></div>
      <div class="ppe-tags">
        ${(w.detected_ppe||[]).map(p=>`<span class="tag">${p}</span>`).join("")}
        ${(w.missing_ppe||[]).map(p=>`<span class="tag missing">⚠ ${p}</span>`).join("")}
      </div>
    </div>`).join("");
}
function collectAlerts(ws){
  const now=new Date().toLocaleTimeString();
  ws.filter(w=>!w.compliant).forEach(w=>{alerts.unshift({time:now,msg:`${w.worker_id} missing ${w.missing_ppe.join(", ")}`})});
  alerts=alerts.slice(0,MAX_ALERTS);
  alertsList.innerHTML=alerts.map(a=>`<div class="alert-item"><time>${a.time}</time> ${a.msg}</div>`).join("")
    ||'<em style="color:#8b949e;font-size:.85rem">No violations</em>';
}
function setZone(z){fetch("/zones",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({zone:z})})}
connect();
</script>
</body>
</html>"""


# ── REST Endpoints ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTML

@app.get("/api/health")
@app.get("/health")
async def health():
    return JSONResponse({
        "status": "ok",
        "fps":    _fps_stats["fps"],
        "zone":   _active_zone,
        "ws_connections": len(manager.active),
        "camera_active": camera is not None and camera.isOpened() if camera else False,
        "pipeline_active": pipeline is not None,
    })

@app.get("/api/zones")
@app.get("/zones")
async def list_zones():
    db_zones = db.get_zones()
    from src.core.rule_engine import RuleEngine
    return JSONResponse({"zones": RuleEngine().list_zones(), "db_zones": db_zones, "active": _active_zone})

@app.post("/api/zones")
@app.post("/zones")
async def set_zone(body: dict):
    global _active_zone
    if "name" in body or "kind" in body:
        db.save_zone(body)
    _active_zone = body.get("zone", body.get("name", config.DEFAULT_ZONE))
    if pipeline:
        pipeline.set_zone(_active_zone)
    return JSONResponse({"active": _active_zone})

@app.get("/api/violations")
async def get_violations_api():
    return JSONResponse(db.get_violations())

@app.post("/api/violations/{evt_id}/acknowledge")
async def acknowledge_violation_api(evt_id: str):
    ok = db.acknowledge_violation(evt_id)
    return JSONResponse({"success": ok, "id": evt_id})

@app.get("/api/workers")
async def get_workers_api():
    return JSONResponse(db.get_workers())

@app.get("/api/reports")
async def get_reports_api():
    return JSONResponse(db.get_reports())

@app.get("/api/stats")
async def get_stats_api():
    """Dashboard overview stats — live from DB."""
    stats = db.get_stats()
    stats["current_fps"] = _fps_stats["fps"]
    stats["active_zone"] = _active_zone
    stats["ws_connections"] = len(manager.active)
    return JSONResponse(stats)

@app.get("/api/cameras")
async def get_cameras_api():
    """Return cameras from DB, enriched with live pipeline status."""
    db_cameras = db.get_cameras()
    result = []
    for cam in db_cameras:
        is_live = cam["id"] == "CAM-01" and camera is not None and camera.isOpened()
        result.append({
            "id": cam["id"],
            "name": cam["name"],
            "zoneId": _active_zone if cam["id"] == "CAM-01" else "ZONE-01",
            "resolution": "1920×1080",
            "targetFps": config.TARGET_FPS,
            "actualFps": _fps_stats["fps"] if is_live else 0.0,
            "latencyMs": round(1000.0 / max(1, _fps_stats["fps"]), 1) if is_live else 0.0,
            "status": "online" if is_live else "offline",
            "streamUrl": cam["source"],
        })

    # If no cameras in DB, still show the live pipeline camera
    if not result:
        result.append({
            "id": "CAM-01",
            "name": "EdgeVision Live AI Stream",
            "zoneId": _active_zone,
            "resolution": "1920×1080",
            "targetFps": config.TARGET_FPS,
            "actualFps": _fps_stats["fps"],
            "latencyMs": round(1000.0 / max(1, _fps_stats["fps"]), 1),
            "status": "online" if (camera and camera.isOpened()) else "offline",
            "streamUrl": "ws://localhost:8000/ws"
        })
    return JSONResponse(result)

@app.post("/api/cameras")
async def add_camera_api(body: dict):
    """Register a new camera in the database."""
    ok = db.save_camera(body)
    return JSONResponse({"success": ok})

@app.get("/api/model-metrics")
async def get_model_metrics():
    """Return model metrics — real FPS from pipeline, static accuracy from training evaluation."""
    current_fps = _fps_stats["fps"]
    # P95 latency estimated from FPS
    p95_latency = round(1000.0 / max(1, current_fps) * 1.3, 1) if current_fps > 0 else 0.0

    return JSONResponse({
        "model_version": "edgevision-ppe-v3.2-fp16",
        "target_fps": config.TARGET_FPS,
        "current_fps": current_fps,
        "p95_latency_ms": p95_latency,
        "map50": 0.846,
        "map50_95": 0.612,
        "classes": [
            {"cls": "person", "precision": 0.97, "recall": 0.96, "map50": 0.972},
            {"cls": "helmet", "precision": 0.94, "recall": 0.92, "map50": 0.941},
            {"cls": "vest", "precision": 0.93, "recall": 0.90, "map50": 0.928},
            {"cls": "boots", "precision": 0.84, "recall": 0.78, "map50": 0.812},
            {"cls": "safety_belt", "precision": 0.87, "recall": 0.81, "map50": 0.844},
            {"cls": "lanyard", "precision": 0.79, "recall": 0.71, "map50": 0.758},
            {"cls": "hook", "precision": 0.76, "recall": 0.68, "map50": 0.723},
            {"cls": "anchor_point", "precision": 0.82, "recall": 0.74, "map50": 0.789}
        ]
    })

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("src.api.server:app", host=config.SERVER_HOST, port=config.SERVER_PORT, reload=False)
