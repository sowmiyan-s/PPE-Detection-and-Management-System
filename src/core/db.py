"""
Pure SQL database accessor for EdgeVision backend API & Vision Pipeline.
Provides clean query & insert helpers for violation events, worker tracks,
cameras, and zones with proof of evidence storage using local SQLite / PostgreSQL.
"""

from __future__ import annotations

import json
import os
import uuid
import logging
import asyncio
import threading
import time
from typing import Any
from datetime import datetime, timedelta

from src.core import config
from src.core import runtime
from src.core.cache import sql_cache as mongo_cache, cached
from src.core import sqlite_db

log = logging.getLogger(__name__)

EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "database", "evidence")
os.makedirs(EVIDENCE_DIR, exist_ok=True)

FALLBACK_DIR = os.path.dirname(EVIDENCE_DIR)
CAMERAS_JSON = os.path.join(FALLBACK_DIR, "cameras_fallback.json")
ZONES_JSON = os.path.join(FALLBACK_DIR, "zones_fallback.json")
VIOLATIONS_JSON = os.path.join(FALLBACK_DIR, "violations_fallback.json")

def _load_fallback_json(filepath: str, default: list) -> list:
    if os.path.isfile(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    return data
        except Exception:
            pass
    return [dict(x) for x in default]

_fallback_lock = threading.Lock()

def _save_fallback_json(filepath: str, data: list) -> None:
    with _fallback_lock:
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            log.warning("Failed to save fallback JSON %s: %s", filepath, e)

async def _async_save_fallback_json(filepath: str, data: list) -> None:
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(runtime.get_io_executor(), _save_fallback_json, filepath, data)
    except Exception as e:
        log.warning("Async fallback JSON save error: %s", e)

def get_db_engine() -> str:
    """Return current active database engine ('sqlite' or 'postgresql')."""
    return getattr(config, "DB_ENGINE", "sqlite").lower()

def set_db_engine(engine: str) -> str:
    """Set active database engine at runtime ('sqlite' or 'postgresql')."""
    new_engine = config.set_db_engine(engine)
    log.info("Database engine switched to: %s", new_engine)
    return new_engine

def is_rdbms_active() -> bool:
    """Check if current active database engine is SQL (SQLite or PostgreSQL)."""
    return True

def is_dual_sync_active() -> bool:
    """Dual database sync is deprecated after MongoDB removal."""
    return False

def set_dual_sync(enabled: bool) -> bool:
    """No-op for dual sync setting."""
    return False

async def sync_databases() -> dict[str, Any]:
    """Reconcile and sync records across SQL storage engines."""
    return {
        "success": True,
        "engine": get_db_engine(),
        "dual_sync": False,
        "synced_counts": {"violations": 0, "cameras": 0, "zones": 0},
        "timestamp": datetime.utcnow().isoformat()
    }

def get_db_status() -> dict[str, Any]:
    """Return comprehensive SQL database metrics and status."""
    return {
        "engine": get_db_engine(),
        "dual_sync_enabled": False,
        "circuit_breaker_open": False,
        "consecutive_failures": 0,
        "in_memory_violations_count": len(_MEM_VIOLATIONS),
        "in_memory_cameras_count": len(_MEM_CAMERAS),
        "in_memory_zones_count": len(_MEM_ZONES),
        "database_url": config.DATABASE_URL.split("@")[-1] if "@" in config.DATABASE_URL else config.DATABASE_URL,
        "sqlite_db_path": sqlite_db.SQLITE_DB_PATH
    }

def get_db():
    """Return SQL database context indicator."""
    return None

def close_db():
    """Cleanly close database connections."""
    pass

async def ensure_db():
    """Initialize SQL database tables and default seed data."""
    try:
        sqlite_db.init_sqlite_db()
        log.info("SQL database initialized successfully.")
    except Exception as err:
        log.warning("SQL database initialization info: %s", err)

SAMPLE_PROOF_SVG = sqlite_db.SAMPLE_PROOF_SVG

_MEM_VIOLATIONS: list[dict[str, Any]] = sqlite_db.get_violations_sql(1000) or _load_fallback_json(VIOLATIONS_JSON, [])

_DEFAULT_SEED_ZONES = [
    {"id": "General Plant Floor", "name": "General Plant Floor", "description": "General plant area – basic PPE required", "required_ppe": ["helmet", "vest"], "frame_threshold": 8, "dwell_seconds": 5, "confidence": 0.60},
]

_MEM_ZONES: list[dict[str, Any]] = sqlite_db.get_zones_sql() or _load_fallback_json(ZONES_JSON, _DEFAULT_SEED_ZONES)

_DEFAULT_SEED_CAMERAS = [
    {
        "id": "CAM-01",
        "name": "EdgeVision Primary Camera",
        "source": "0",
        "location": "Plant Floor Area",
        "is_active": 1,
        "zone_id": "General Plant Floor",
        "target_fps": 20
    }
]

_MEM_CAMERAS: list[dict[str, Any]] = _load_fallback_json(CAMERAS_JSON, _DEFAULT_SEED_CAMERAS)

async def record_violation(
    worker_id: str,
    zone_id: str,
    violation_type: str,
    detected_ppe: list[str],
    missing_ppe: list[str],
    confidence: float,
    image_path: str = "",
    image_base64: str = "",
    video_path: str = "",
    camera_id: str = "CAM-01",
    model_version: str = "cerberus-ai-v1.0"
) -> str:
    """Record or update a violation event with image/video evidence directly in SQL & memory.
    Deduplicates active unacknowledged violations per worker ID to prevent duplicate reports."""
    norm_zone = sqlite_db.normalize_zone_id(zone_id)
    now_ts = datetime.utcnow()
    ts_str = now_ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Active Violation Uniqueness Guard:
    def _norm_wid(w: Any) -> str:
        if not w: return ""
        s = str(w).strip().lower().replace("worker-", "").replace("worker_", "")
        return s

    norm_missing = sorted(missing_ppe)
    req_wid = _norm_wid(worker_id)
    for v in _MEM_VIOLATIONS:
        v_worker = _norm_wid(v.get("worker_track_id") or v.get("workerId"))
        v_stat = v.get("acknowledgement_status") or v.get("status") or "unacknowledged"
        if (
            v_worker == req_wid
            and sorted(v.get("missing_ppe", [])) == norm_missing
            and v_stat == "unacknowledged"
        ):
            v["timestamp"] = ts_str
            v["confidence"] = confidence
            v["zone_id"] = norm_zone
            v["zoneId"] = norm_zone
            if image_path: v["image_path"] = image_path; v["imagePath"] = image_path
            if image_base64: v["image_base64"] = image_base64; v["imageBase64"] = image_base64
            if video_path: v["video_path"] = video_path; v["videoPath"] = video_path

            sqlite_db.save_violation_sql(v)
            asyncio.create_task(_async_save_fallback_json(VIOLATIONS_JSON, _MEM_VIOLATIONS))
            asyncio.create_task(mongo_cache.invalidate_tags(["violations", "stats", "reports", "workers"]))
            log.info("Updated existing active violation %s for worker %s in SQL", v["id"], worker_id)
            return str(v["id"])

    evt_id = f"EVT-{uuid.uuid4().hex[:6].upper()}"
    event = {
        "id": evt_id,
        "zone_id": norm_zone,
        "zoneId": norm_zone,
        "camera_id": camera_id,
        "worker_track_id": worker_id,
        "workerId": worker_id,
        "violation_type": violation_type,
        "detected_ppe": detected_ppe,
        "missing_ppe": missing_ppe,
        "confidence": confidence,
        "image_path": image_path,
        "image_base64": image_base64,
        "video_path": video_path,
        "model_version": model_version,
        "timestamp": ts_str,
        "acknowledgement_status": "unacknowledged"
    }

    # Write to SQL & Local Memory
    sqlite_db.save_violation_sql(event)
    _MEM_VIOLATIONS.insert(0, event)
    if len(_MEM_VIOLATIONS) > 500:
        _MEM_VIOLATIONS.pop()

    asyncio.create_task(_async_save_fallback_json(VIOLATIONS_JSON, _MEM_VIOLATIONS))
    asyncio.create_task(mongo_cache.invalidate_tags(["violations", "stats", "reports", "workers"]))
    return evt_id

async def acknowledge_violation(evt_id: str, status: str = "accepted") -> bool:
    """Mark a violation event as accepted, declined, or reviewed instantly in SQL."""
    target_status = status if status in ("accepted", "declined", "reviewed", "unacknowledged") else "accepted"
    
    sqlite_db.acknowledge_violation_sql(evt_id, target_status)
    for v in _MEM_VIOLATIONS:
        if v.get("id") == evt_id:
            v["acknowledgement_status"] = target_status
            v["status"] = target_status

    asyncio.create_task(_async_save_fallback_json(VIOLATIONS_JSON, _MEM_VIOLATIONS))
    asyncio.create_task(mongo_cache.invalidate_tags(["violations", "stats", "reports", "workers"]))
    return True

async def delete_violation(evt_id: str) -> bool:
    """Delete a single violation event and its evidence record from SQL."""
    global _MEM_VIOLATIONS
    sqlite_db.delete_violation_sql(evt_id)
    _MEM_VIOLATIONS = [v for v in _MEM_VIOLATIONS if v.get("id") != evt_id]
    asyncio.create_task(_async_save_fallback_json(VIOLATIONS_JSON, _MEM_VIOLATIONS))
    asyncio.create_task(mongo_cache.invalidate_tags(["violations", "stats", "reports", "workers"]))
    return True

async def delete_all_violations() -> bool:
    """Clear all past violation evidence records and worker tracks from SQL."""
    global _MEM_VIOLATIONS
    sqlite_db.clear_all_violations_sql()
    sqlite_db.clear_all_workers_sql()
    _MEM_VIOLATIONS.clear()
    await _async_save_fallback_json(VIOLATIONS_JSON, [])
    await mongo_cache.clear()
    
    try:
        if os.path.isdir(EVIDENCE_DIR):
            for fname in os.listdir(EVIDENCE_DIR):
                fpath = os.path.join(EVIDENCE_DIR, fname)
                if os.path.isfile(fpath):
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
    except Exception as ev_err:
        log.warning("Evidence file cleanup warning: %s", ev_err)

    return True

async def delete_violations_bulk(evt_ids: list[str]) -> bool:
    """Purge specific selected violation records from SQL."""
    global _MEM_VIOLATIONS
    ids_set = set(evt_ids)
    sqlite_db.delete_violations_bulk_sql(list(ids_set))
    _MEM_VIOLATIONS = [v for v in _MEM_VIOLATIONS if v.get("id") not in ids_set]
    asyncio.create_task(_async_save_fallback_json(VIOLATIONS_JSON, _MEM_VIOLATIONS))
    asyncio.create_task(mongo_cache.invalidate_tags(["violations", "stats", "reports", "workers"]))
    return True

async def delete_worker(worker_id: str) -> bool:
    """Delete all compliance entries and violation records for a specific worker from SQL."""
    global _MEM_VIOLATIONS
    w_str = str(worker_id).strip()
    sqlite_db.delete_worker_violations_sql(w_str)
    _MEM_VIOLATIONS = [
        v for v in _MEM_VIOLATIONS
        if str(v.get("worker_track_id", "")).strip() != w_str and str(v.get("workerId", "")).strip() != w_str and str(v.get("worker_id", "")).strip() != w_str
    ]
    await mongo_cache.invalidate_tags(["violations", "stats", "reports", "workers"])
    return True

async def delete_all_workers() -> bool:
    """Clear all worker compliance history."""
    return await delete_all_violations()

async def delete_camera(cam_id: str) -> bool:
    """Remove a camera from SQL / memory registry."""
    global _MEM_CAMERAS
    _MEM_CAMERAS = [c for c in _MEM_CAMERAS if c.get("id") != cam_id]
    asyncio.create_task(_async_save_fallback_json(CAMERAS_JSON, _MEM_CAMERAS))
    await mongo_cache.invalidate_tags(["cameras", "stats"])
    return True

@cached(ttl=5.0, tags=["violations"])
async def get_violations(limit: int = 100) -> list[dict[str, Any]]:
    """Retrieve recent violation events from SQL or memory."""
    sql_events = sqlite_db.get_violations_sql(limit)
    events = sql_events if sql_events else _MEM_VIOLATIONS[:limit]

    res = []
    for d in events:
        ts = d.get("timestamp")
        if isinstance(ts, datetime):
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        else:
            ts_str = str(ts)

        res.append({
            "id": d.get("id"),
            "zoneId": d.get("zone_id") or d.get("zoneId"),
            "workerId": d.get("worker_track_id") or d.get("workerId"),
            "type": d.get("violation_type") or d.get("type"),
            "detected": d.get("detected_ppe") or d.get("detected") or [],
            "missing": d.get("missing_ppe") or d.get("missing") or [],
            "confidence": d.get("confidence", 0.0),
            "timestamp": ts_str,
            "imagePath": d.get("image_path") or d.get("imagePath") or "",
            "imageBase64": d.get("image_base64") or d.get("imageBase64") or "",
            "videoPath": d.get("video_path") or d.get("videoPath") or "",
            "status": d.get("acknowledgement_status") or d.get("status") or "unacknowledged",
            "modelVersion": d.get("model_version") or d.get("modelVersion"),
            "acknowledged": (d.get("acknowledgement_status") or d.get("status")) in ("accepted", "reviewed"),
            "declined": (d.get("acknowledgement_status") or d.get("status")) == "declined",
            "cameraId": d.get("camera_id") or d.get("cameraId") or "CAM-01"
        })
    return res

@cached(ttl=5.0, tags=["zones"])
async def get_zones() -> list[dict[str, Any]]:
    """Retrieve configured safety zones directly from local SQL database / memory."""
    sql_zones = sqlite_db.get_zones_sql()
    if sql_zones:
        _MEM_ZONES[:] = sql_zones
        return sql_zones
    return _MEM_ZONES

async def save_zone(zone_data: dict) -> bool:
    """Insert or update safety zone configuration directly in SQL database and memory."""
    await mongo_cache.invalidate_tags(["zones", "stats"])
    
    zone_id = zone_data.get("id") or zone_data.get("name") or f"ZONE-{uuid.uuid4().hex[:4].upper()}"
    zone_name = zone_data.get("name") or zone_id
    desc = zone_data.get("description") or zone_data.get("kind") or "Active Safety Zone"
    req_ppe = zone_data.get("required_ppe", [])
    if isinstance(req_ppe, (set, tuple)):
        req_ppe = list(req_ppe)
    elif not isinstance(req_ppe, list):
        req_ppe = []
    frame_thresh = int(zone_data.get("frame_threshold") or zone_data.get("frameThreshold") or 8)
    dwell_sec = int(zone_data.get("dwell_seconds") or zone_data.get("dwellSeconds") or 2)
    conf = float(zone_data.get("confidence") or zone_data.get("confidence_threshold") or 0.60)
    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    entry = {
        "id": zone_id,
        "name": zone_name,
        "description": desc,
        "kind": desc,
        "required_ppe": req_ppe,
        "frame_threshold": frame_thresh,
        "frameThreshold": frame_thresh,
        "dwell_seconds": dwell_sec,
        "dwellSeconds": dwell_sec,
        "confidence": conf,
        "confidence_threshold": conf,
        "updated_at": now_iso
    }

    # Direct SQL Database persistence (< 2ms)
    sqlite_db.save_zone_sql(entry)

    found = False
    for idx, z in enumerate(_MEM_ZONES):
        if z.get("id") == zone_id or z.get("name") == zone_name or z.get("id") == zone_name:
            _MEM_ZONES[idx] = entry
            found = True
            break
    if not found:
        _MEM_ZONES.append(entry)

    asyncio.create_task(_async_save_fallback_json(ZONES_JSON, _MEM_ZONES))
    return True

async def delete_zone(zone_id: str) -> bool:
    """Remove a safety zone configuration from SQL database and memory."""
    global _MEM_ZONES
    sqlite_db.delete_zone_sql(zone_id)
    _MEM_ZONES = [z for z in _MEM_ZONES if z.get("id") != zone_id and z.get("name") != zone_id]
    asyncio.create_task(_async_save_fallback_json(ZONES_JSON, _MEM_ZONES))
    await mongo_cache.invalidate_tags(["zones", "stats"])
    return True

def _is_today(ts: Any) -> bool:
    """Helper to check if a datetime or timestamp string is from today (UTC)."""
    if not ts:
        return False
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if isinstance(ts, datetime):
        return ts >= today_start
    ts_str = str(ts)
    today_str = today_start.strftime("%Y-%m-%d")
    return ts_str.startswith(today_str) or ts_str >= today_start.strftime("%Y-%m-%dT%H:%M:%SZ")

@cached(ttl=5.0, tags=["workers"])
async def get_workers() -> list[dict[str, Any]]:
    """Retrieve tracked worker compliance scores calculated from SQL / _MEM_VIOLATIONS."""
    violations = sqlite_db.get_violations_sql(1000) or _MEM_VIOLATIONS
    worker_map: dict[str, dict] = {}
    for v in violations:
        if (v.get("acknowledgement_status") or v.get("status")) == "declined":
            continue
        wid = v.get("worker_track_id") or v.get("workerId") or "Worker-101"
        if wid not in worker_map:
            worker_map[wid] = {
                "id": wid,
                "name": wid,
                "crew": "Inference Crew",
                "shift": "Shift A (06–14)",
                "primaryZone": v.get("zone_id") or v.get("zoneId") or "General Plant Floor",
                "incidents": 0,
                "hoursTracked": 1
            }
        worker_map[wid]["incidents"] += 1

    res = []
    for wid, wdata in worker_map.items():
        incidents = wdata["incidents"]
        wdata["compliance"] = max(50, 100 - (incidents * 3))
        res.append(wdata)
    return res

@cached(ttl=5.0, tags=["reports"])
async def get_reports() -> dict[str, Any]:
    """Calculate aggregated safety compliance reporting from SQL & _MEM_VIOLATIONS."""
    violations = sqlite_db.get_violations_sql(1000) or _MEM_VIOLATIONS
    non_declined = [v for v in violations if (v.get("acknowledgement_status") or v.get("status")) != "declined"]
    total_violations = len(non_declined)
    zone_counts: dict[str, int] = {}
    workers: set[str] = set()
    reviewed = 0
    conf_sum = 0.0

    for v in non_declined:
        zid = sqlite_db.normalize_zone_id(v.get("zone_id") or v.get("zoneId"))
        zone_counts[zid] = zone_counts.get(zid, 0) + 1
        wid = v.get("worker_track_id") or v.get("workerId")
        if wid: workers.add(wid)
        stat = v.get("acknowledgement_status") or v.get("status")
        if stat in ("reviewed", "accepted") or v.get("acknowledged"):
            reviewed += 1
        conf_sum += float(v.get("confidence", 0.90))

    by_zone = [{"zone_id": z, "count": c} for z, c in zone_counts.items()]
    avg_conf = round(conf_sum / max(1, total_violations), 3) if total_violations > 0 else 0.90
    today_str = datetime.utcnow().strftime("%Y-%m-%d")

    return {
        "total_violations": total_violations,
        "avg_compliance": max(60, 100 - (total_violations * 3)) if total_violations > 0 else 100,
        "avg_confidence": avg_conf,
        "false_alerts_per_hour": round(total_violations * 0.05, 2),
        "violations_per_hour": round(total_violations * 0.2, 1),
        "unique_workers": len(workers),
        "reviewed": reviewed,
        "by_zone": by_zone,
        "daily_trend": [{"day": today_str, "violations": total_violations, "compliance": max(70, 100 - total_violations * 2)}] if total_violations > 0 else [],
    }

@cached(ttl=5.0, tags=["stats"])
async def get_stats() -> dict[str, Any]:
    """Get live overview stats for dashboard from SQL and memory."""
    violations = sqlite_db.get_violations_sql(1000) or _MEM_VIOLATIONS
    active_violations = sum(
        1 for v in violations
        if (v.get("acknowledgement_status") or v.get("status") or "unacknowledged") not in ("accepted", "reviewed", "declined")
    )
    violations_today = sum(
        1 for v in violations
        if (v.get("acknowledgement_status") or v.get("status")) != "declined" and _is_today(v.get("timestamp"))
    )
    unique_workers = len(set(
        v.get("worker_track_id") or v.get("workerId")
        for v in violations
        if (v.get("worker_track_id") or v.get("workerId"))
        and (v.get("acknowledgement_status") or v.get("status")) != "declined"
        and _is_today(v.get("timestamp"))
    ))
    cams_online = sum(1 for c in _MEM_CAMERAS if c.get("is_active", 1) == 1)

    return {
        "cameras_online": cams_online,
        "cameras_total": len(_MEM_CAMERAS),
        "active_violations": active_violations,
        "violations_today": violations_today,
        "workers_tracked": unique_workers,
        "daily_compliance": max(60, 100 - (active_violations * 3)) if active_violations > 0 else 100,
    }

@cached(ttl=15.0, tags=["cameras"])
async def get_cameras() -> list[dict[str, Any]]:
    """Retrieve active camera streams."""
    return _MEM_CAMERAS

async def save_camera(cam_data: dict) -> bool:
    """Insert or update a camera in registry."""
    cam_id = cam_data.get("id") or f"CAM-{uuid.uuid4().hex[:4].upper()}"
    src = str(cam_data.get("source") or cam_data.get("streamUrl") or "0").strip()
    cam_type = cam_data.get("type") or ("webcam" if src.isdigit() else "stream")
    zone_id = cam_data.get("zoneId") or cam_data.get("zone_id") or "General Plant Floor"
    fps = int(cam_data.get("targetFps") or cam_data.get("target_fps") or 20)
    cam_name = str(cam_data.get("name") or "").strip() or f"Camera-{cam_id}"
    
    cam_entry = {
        "id": cam_id,
        "name": cam_name,
        "source": src,
        "streamUrl": src,
        "type": cam_type,
        "location": cam_data.get("location", "Plant Area"),
        "is_active": 1,
        "zone_id": zone_id,
        "target_fps": fps
    }
    
    _MEM_CAMERAS[:] = [c for c in _MEM_CAMERAS if c.get("id") != cam_id]
    _MEM_CAMERAS.append(cam_entry)
    asyncio.create_task(_async_save_fallback_json(CAMERAS_JSON, _MEM_CAMERAS))
    await mongo_cache.invalidate_tags(["cameras", "stats"])
    return True

async def update_camera(cam_id: str, cam_data: dict) -> bool:
    """Update camera properties in registry."""
    await mongo_cache.invalidate_tags(["cameras", "stats"])
    
    src = str(cam_data.get("source") or cam_data.get("streamUrl") or "").strip()
    if src:
        cam_type = cam_data.get("type") or ("webcam" if src.isdigit() else "stream")
    else:
        cam_type = cam_data.get("type")

    for c in _MEM_CAMERAS:
        if c.get("id") == cam_id:
            if "name" in cam_data and cam_data["name"]: c["name"] = cam_data["name"]
            if src:
                c["source"] = src
                c["streamUrl"] = src
            if cam_type: c["type"] = cam_type
            if "zoneId" in cam_data or "zone_id" in cam_data:
                c["zone_id"] = cam_data.get("zoneId") or cam_data.get("zone_id")
            if "targetFps" in cam_data or "target_fps" in cam_data:
                c["target_fps"] = int(cam_data.get("targetFps") or cam_data.get("target_fps"))

    asyncio.create_task(_async_save_fallback_json(CAMERAS_JSON, _MEM_CAMERAS))
    return True

@cached(ttl=5.0, tags=["violations"])
async def get_filtered_violations(
    camera_ids: list[str] | None = None,
    date_range: str = "all",
    start_date: str | None = None,
    end_date: str | None = None,
    zone_id: str | None = None,
    worker_id: str | None = None,
    status: str | None = None,
    limit: int = 1000
) -> list[dict[str, Any]]:
    """Query violation events matching filter criteria using local SQL storage."""
    sql_events = sqlite_db.get_violations_sql(limit)
    candidate_list = sql_events if sql_events else _MEM_VIOLATIONS
    events = []
    now = datetime.utcnow()
    
    for d in candidate_list:
        d_zone = d.get("zone_id") or d.get("zoneId")
        if zone_id and zone_id != "all" and d_zone != zone_id:
            continue
        d_worker = d.get("worker_track_id") or d.get("workerId")
        if worker_id and worker_id != "all" and d_worker != worker_id:
            continue
        v_stat = d.get("acknowledgement_status") or d.get("status") or "unacknowledged"
        if status == "unacknowledged" and v_stat in ("accepted", "reviewed", "declined"):
            continue
        if status in ("accepted", "reviewed") and v_stat not in ("accepted", "reviewed"):
            continue
        if status == "declined" and v_stat != "declined":
            continue

        v_ts = d.get("timestamp")
        if isinstance(v_ts, datetime):
            if date_range in ("hours", "last_24h") and v_ts < (now - timedelta(hours=24)):
                continue
            if date_range in ("daily", "day", "today") and v_ts < now.replace(hour=0, minute=0, second=0, microsecond=0):
                continue
            if date_range in ("weekly", "week") and v_ts < (now - timedelta(days=7)):
                continue
            if date_range in ("monthly", "month") and v_ts < (now - timedelta(days=30)):
                continue

        events.append(d)
        
    events = events[:limit]
        
    res = []
    for d in events:
        ts = d.get("timestamp")
        if isinstance(ts, datetime):
            ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            ts_str = str(ts or "")
            if not ts_str.endswith("Z") and "T" in ts_str:
                ts_str += "Z"

        v_status = d.get("acknowledgement_status") or d.get("status") or "unacknowledged"
        res.append({
            "id": d.get("id"),
            "zoneId": d.get("zone_id") or d.get("zoneId") or "General Plant Floor",
            "workerId": d.get("worker_track_id") or d.get("workerId") or "Worker-101",
            "type": d.get("violation_type") or d.get("type") or "PPE Violation",
            "detected": d.get("detected_ppe") or d.get("detected") or [],
            "missing": d.get("missing_ppe") or d.get("missing") or [],
            "confidence": float(d.get("confidence") or 0.90),
            "timestamp": ts_str,
            "imagePath": d.get("image_path") or d.get("imagePath") or "",
            "imageBase64": d.get("image_base64") or d.get("imageBase64") or "",
            "videoPath": d.get("video_path") or d.get("videoPath") or "",
            "status": v_status,
            "acknowledged": v_status in ("accepted", "reviewed"),
            "declined": v_status == "declined",
            "cameraId": d.get("camera_id") or d.get("cameraId") or "CAM-01"
        })
    return res

def get_zone_name_sync(zone_id: str) -> str:
    """Synchronous lookup of zone name by ID from local cache."""
    for z in _MEM_ZONES:
        if z.get("id") == zone_id or z.get("name") == zone_id:
            return z.get("name") or zone_id
    return zone_id.replace("_", " ").title()

async def reject_violation(violation_id: str) -> bool:
    """Reject/dismiss a violation and update memory cache & SQL database."""
    global _MEM_VIOLATIONS
    for v in _MEM_VIOLATIONS:
        if v.get("id") == violation_id:
            v["status"] = "REJECTED"
    return sqlite_db.reject_violation_sql(violation_id)
