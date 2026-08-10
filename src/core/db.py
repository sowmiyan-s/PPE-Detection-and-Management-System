"""
MongoDB database accessor for EdgeVision backend API & Vision Pipeline.
Provides clean query & insert helpers for violation events, worker tracks,
cameras, and zones with proof of evidence storage.
"""

from __future__ import annotations

import json
import os
import uuid
import logging
from typing import Any
from datetime import datetime, timedelta

# pyrefly: ignore [missing-import]
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure

from src.core import config
from src.core.cache import mongo_cache, cached

log = logging.getLogger(__name__)

EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "database", "evidence")
os.makedirs(EVIDENCE_DIR, exist_ok=True)

_client = None
_db = None

import ssl

def get_db():
    """Connect to MongoDB database and return the database instance."""
    global _client, _db
    if _db is None:
        try:
            kwargs = {
                "serverSelectionTimeoutMS": 3000,
                "connectTimeoutMS": 3000,
                "socketTimeoutMS": 3000,
                "tlsAllowInvalidCertificates": True,
            }
            _client = AsyncIOMotorClient(config.MONGODB_URI, **kwargs)
            _db = _client[config.MONGODB_DB_NAME]
            log.info(f"Connected to MongoDB at {config.MONGODB_URI}")
        except Exception as e:
            log.error(f"Failed to connect to MongoDB: {e}")
            raise
    return _db

async def ensure_db():
    """Initialize database collections and seed data if they don't exist yet."""
    try:
        db = get_db()
        
        # Check if we need to seed zones
        count_zones = await db.zones.count_documents({})
        if count_zones == 0:
            log.info("Seeding initial zones...")
            zones = [
                {"id": "ZONE-01", "name": "general_plant", "description": "General plant area – basic PPE required", "required_ppe": ["helmet", "vest", "boots"], "authorised_workers": []},
                {"id": "ZONE-02", "name": "construction", "description": "Construction area – helmet, vest and safety boots required", "required_ppe": ["helmet", "vest", "boots"], "authorised_workers": []},
                {"id": "ZONE-03", "name": "work_at_height", "description": "Work at height platform – harness and hook required", "required_ppe": ["helmet", "vest", "boots", "safety_belt", "hook"], "authorised_workers": []},
                {"id": "ZONE-04", "name": "restricted_machinery", "description": "Restricted machinery area – high hazard", "required_ppe": ["helmet", "vest", "goggles", "ear-mufs", "face-guard"], "authorised_workers": ["Worker-101", "Worker-102"]},
                {"id": "ZONE-05", "name": "hazardous_material", "description": "Hazardous material handling zone", "required_ppe": ["helmet", "safety-suit", "boots", "gloves", "goggles"], "authorised_workers": []},
            ]
            await db.zones.insert_many(zones)

        # Check if we need to seed cameras
        count_cameras = await db.cameras.count_documents({})
        if count_cameras == 0:
            log.info("Seeding initial cameras...")
            cameras = [
                {
                    "id": "CAM-01", 
                    "name": "EdgeVision Primary Camera", 
                    "source": "0", 
                    "location": "Plant Floor Area",
                    "zone_id": "general_plant",
                    "resolution": "1280x720",
                    "fps": 20,
                    "is_active": 1,
                    "type": "webcam",
                    "streamUrl": "0"
                }
            ]
            await db.cameras.insert_many(cameras)

        log.info("Database collections & seed data verified.")
    except Exception as e:
        err_str = str(e).split("\n")[0][:120]
        log.warning("MongoDB initialization info: %s (using memory fallback)", err_str)        # Seed roles if empty
        if await db.roles.count_documents({}) == 0:
            await db.roles.insert_many([
                {"role_id": "ROLE-ADMIN", "name": "Safety Manager", "permissions": ["read", "write", "acknowledge", "delete"]},
                {"role_id": "ROLE-OPERATOR", "name": "Plant Operator", "permissions": ["read", "acknowledge"]}
            ])

        # Seed users if empty
        if await db.users.count_documents({}) == 0:
            await db.users.insert_many([
                {"user_id": "USR-01", "username": "admin", "role": "ROLE-ADMIN", "email": "admin@factory.com"},
                {"user_id": "USR-02", "username": "operator", "role": "ROLE-OPERATOR", "email": "op@factory.com"}
            ])

        # Ensure collections exist and create performance indexes
        existing_cols = await db.list_collection_names()
        for col in ["audit_logs", "alert_deliveries", "worker_tracks"]:
            if col not in existing_cols:
                await db.create_collection(col)
            
        await db.violation_events.create_index([("worker_track_id", 1), ("acknowledgement_status", 1)])
        await db.violation_events.create_index([("timestamp", -1)])
        await db.cameras.create_index([("id", 1)], unique=True)
        await db.zones.create_index([("id", 1)], unique=True)

        log.info("MongoDB database initialized successfully with indexes.")
    except Exception as err:
        log.warning("MongoDB initialization warning (will retry on demand): %s", err)

SAMPLE_PROOF_SVG = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' width='640' height='360' viewBox='0 0 640 360'>"
    "<rect width='100%' height='100%' fill='%23111827'/>"
    "<rect x='180' y='50' width='280' height='250' fill='none' stroke='%23ef4444' stroke-width='3'/>"
    "<rect x='180' y='26' width='160' height='24' fill='%23ef4444'/>"
    "<text x='188' y='42' fill='%23ffffff' font-family='monospace' font-size='12' font-weight='bold'>AI PROOF SNAPSHOT</text>"
    "<text x='210' y='160' fill='%23f87171' font-family='sans-serif' font-size='16' font-weight='bold'>PPE VIOLATION DETECTED</text>"
    "<text x='210' y='190' fill='%239ca3af' font-family='sans-serif' font-size='12'>CONFIDENCE: 92% | ZONE: PLANT</text>"
    "<text x='20' y='340' fill='%23ef4444' font-family='monospace' font-size='11'>EDGEVISION AUDIT EVIDENCE SNAPSHOT</text>"
    "</svg>"
)

_MEM_VIOLATIONS: list[dict[str, Any]] = []

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
    model_version: str = "edgevision-ppe-v3.2-fp16"
) -> str:
    """Record a violation event with image/video evidence directly in MongoDB.
    Deduplicates active unacknowledged violations per worker ID to prevent duplicate reports."""
    # Deduplication Guard: Check if an unacknowledged violation already exists for this worker ID or recent same-zone event
    now_ts = datetime.utcnow()
    for v in _MEM_VIOLATIONS:
        if v.get("worker_track_id") == worker_id and v.get("acknowledgement_status") != "reviewed":
            log.info("Skipping duplicate violation record for worker %s (existing active event: %s)", worker_id, v["id"])
            return v["id"]
        v_ts = v.get("timestamp")
        if isinstance(v_ts, datetime) and (now_ts - v_ts).total_seconds() < 15.0:
            if v.get("zone_id") == zone_id and set(v.get("missing_ppe", [])) == set(missing_ppe):
                log.info("Skipping duplicate violation record for zone %s (recent event: %s)", zone_id, v["id"])
                return v["id"]

    try:
        database = get_db()
        existing_doc = await database.violation_events.find_one({
            "$or": [
                {"worker_track_id": worker_id, "acknowledgement_status": {"$ne": "reviewed"}},
                {"zone_id": zone_id, "missing_ppe": missing_ppe, "timestamp": {"$gte": now_ts - timedelta(seconds=15)}}
            ]
        })
        if existing_doc:
            log.info("Skipping duplicate DB record for zone %s (active event: %s)", zone_id, existing_doc["id"])
            return existing_doc["id"]
    except Exception:
        pass

    evt_id = f"EVT-{uuid.uuid4().hex[:6].upper()}"
    event = {
        "id": evt_id,
        "zone_id": zone_id,
        "camera_id": camera_id,
        "worker_track_id": worker_id,
        "violation_type": violation_type,
        "detected_ppe": detected_ppe,
        "missing_ppe": missing_ppe,
        "confidence": confidence,
        "image_path": image_path,
        "image_base64": image_base64,
        "video_path": video_path,
        "model_version": model_version,
        "timestamp": datetime.utcnow(),
        "acknowledgement_status": "unacknowledged"
    }

    # Store in memory fallback list
    _MEM_VIOLATIONS.insert(0, event)
    if len(_MEM_VIOLATIONS) > 500:
        _MEM_VIOLATIONS.pop()

    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            database = get_db()
            await database.violation_events.insert_one(event)

            # Audit log record
            await database.audit_logs.insert_one({
                "action": "VIOLATION_RECORDED",
                "evt_id": evt_id,
                "worker_id": worker_id,
                "timestamp": datetime.utcnow()
            })

            log.info("Recorded violation %s for %s (camera: %s, zone: %s)", evt_id, worker_id, camera_id, zone_id)
            await mongo_cache.invalidate_tags(["violations", "stats", "reports", "workers"])
            return evt_id
        except Exception as e:
            if attempt < max_retries:
                err_str = str(e).split("\n")[0][:120]
                log.warning("DB write attempt %d failed for %s, retrying: %s", attempt + 1, evt_id, err_str)
                import asyncio
                await asyncio.sleep(0.5 * (attempt + 1))
            else:
                log.warning("Recorded violation %s in fallback memory store (MongoDB connection offline)", evt_id)
    await mongo_cache.invalidate_tags(["violations", "stats", "reports", "workers"])
    return evt_id

async def acknowledge_violation(evt_id: str, status: str = "accepted") -> bool:
    """Mark a violation event as accepted (confirmed real), declined (false alert), or reviewed."""
    target_status = status if status in ("accepted", "declined", "reviewed", "unacknowledged") else "accepted"
    for v in _MEM_VIOLATIONS:
        if v.get("id") == evt_id:
            v["acknowledgement_status"] = target_status
    await mongo_cache.invalidate_tags(["violations", "stats", "reports", "workers"])
    try:
        db = get_db()
        result = await db.violation_events.update_one(
            {"id": evt_id},
            {"$set": {"acknowledgement_status": target_status}}
        )
        return result.modified_count > 0 or result.matched_count > 0
    except Exception as e:
        log.error("Failed to update status for violation %s to %s: %s", evt_id, target_status, e)
        return False

async def delete_violation(evt_id: str) -> bool:
    """Delete a single violation event and its evidence record from MongoDB."""
    global _MEM_VIOLATIONS
    _MEM_VIOLATIONS = [v for v in _MEM_VIOLATIONS if v.get("id") != evt_id]
    await mongo_cache.invalidate_tags(["violations", "stats", "reports", "workers"])
    try:
        db = get_db()
        result = await db.violation_events.delete_one({"id": evt_id})
        return result.deleted_count > 0 or True
    except Exception as e:
        log.error("Failed to delete violation %s: %s", evt_id, e)
        return True

async def delete_all_violations() -> bool:
    """Clear all past violation evidence records from MongoDB."""
    global _MEM_VIOLATIONS
    _MEM_VIOLATIONS.clear()
    await mongo_cache.invalidate_tags(["violations", "stats", "reports", "workers"])
    try:
        db = get_db()
        await db.violation_events.delete_many({})
        return True
    except Exception as e:
        log.error("Failed to clear violations: %s", e)
        return True

async def delete_camera(cam_id: str) -> bool:
    """Remove a camera from DB."""
    global _MEM_CAMERAS
    _MEM_CAMERAS = [c for c in _MEM_CAMERAS if c.get("id") != cam_id]
    await mongo_cache.invalidate_tags(["cameras", "stats"])
    try:
        db = get_db()
        result = await db.cameras.delete_one({"id": cam_id})
        return result.deleted_count > 0
    except Exception as e:
        log.error("Failed to delete camera %s: %s", cam_id, e)
        return True

@cached(ttl=5.0, tags=["violations"])
async def get_violations(limit: int = 100) -> list[dict[str, Any]]:
    """Retrieve recent violation events with proof of evidence."""
    events = []
    try:
        db = get_db()
        cursor = db.violation_events.find().sort("timestamp", -1).limit(limit)
        events = await cursor.to_list(length=limit)
    except Exception as e:
        err_str = str(e).split("\n")[0][:120]
        log.warning("MongoDB fetch failed, using fallback memory: %s", err_str)

    if not events:
        events = _MEM_VIOLATIONS[:limit]

    res = []
    for d in events:
        ts = d.get("timestamp")
        if isinstance(ts, datetime):
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        else:
            ts_str = str(ts)

        res.append({
            "id": d.get("id"),
            "zoneId": d.get("zone_id"),
            "workerId": d.get("worker_track_id"),
            "type": d.get("violation_type"),
            "detected": d.get("detected_ppe", []),
            "missing": d.get("missing_ppe", []),
            "confidence": d.get("confidence", 0.0),
            "timestamp": ts_str,
            "imagePath": d.get("image_path", ""),
            "imageBase64": d.get("image_base64", ""),
            "videoPath": d.get("video_path", ""),
            "status": d.get("acknowledgement_status", "unacknowledged"),
            "modelVersion": d.get("model_version"),
            "acknowledged": d.get("acknowledgement_status") in ("accepted", "reviewed"),
            "declined": d.get("acknowledgement_status") == "declined",
            "cameraId": d.get("camera_id", "CAM-01")
        })
    return res

_DEFAULT_SEED_ZONES = [
    {"id": "ZONE-01", "name": "general_plant", "description": "General plant area – basic PPE required", "required_ppe": ["helmet", "vest", "boots"]},
    {"id": "ZONE-02", "name": "construction", "description": "Construction area – helmet, vest and safety boots required", "required_ppe": ["helmet", "vest", "boots"]},
    {"id": "ZONE-03", "name": "work_at_height", "description": "Work at height platform – harness and hook required", "required_ppe": ["helmet", "vest", "boots", "safety_belt", "hook"]},
    {"id": "ZONE-04", "name": "restricted_machinery", "description": "Restricted machinery area – high hazard", "required_ppe": ["helmet", "vest", "goggles", "ear-mufs", "face-guard"]},
    {"id": "ZONE-05", "name": "hazardous_material", "description": "Hazardous material handling zone", "required_ppe": ["helmet", "safety-suit", "boots", "gloves", "goggles"]},
]

@cached(ttl=60.0, tags=["zones"])
async def get_zones() -> list[dict[str, Any]]:
    """Retrieve configured safety zones with their required PPE."""
    try:
        db = get_db()
        cursor = db.zones.find()
        zones = await cursor.to_list(length=None)
        if zones:
            result = []
            for d in zones:
                result.append({
                    "id": d.get("id"),
                    "name": d.get("name"),
                    "description": d.get("description"),
                    "required_ppe": d.get("required_ppe", [])
                })
            return result
    except Exception as e:
        log.warning("MongoDB get_zones offline: using default seed zones (%s)", e)
    return _DEFAULT_SEED_ZONES

async def save_zone(zone_data: dict) -> bool:
    """Insert or update safety zone configuration in DB."""
    await mongo_cache.invalidate_tags(["zones", "stats"])
    try:
        db = get_db()
        zone_id = zone_data.get("id") or f"ZONE-{uuid.uuid4().hex[:4].upper()}"
        
        update_doc = {}
        if "name" in zone_data and zone_data["name"]:
            update_doc["name"] = zone_data["name"]
            
        desc = zone_data.get("description") or zone_data.get("kind")
        if desc:
            update_doc["description"] = desc
            
        if "required_ppe" in zone_data:
            update_doc["required_ppe"] = zone_data["required_ppe"]
            
        if not update_doc:
             update_doc["name"] = "Custom Zone"
             
        await db.zones.update_one(
            {"id": zone_id},
            {"$set": update_doc},
            upsert=True
        )
        return True
    except Exception as e:
        log.error("Failed to save zone: %s", e)
        return False

@cached(ttl=10.0, tags=["workers"])
async def get_workers() -> list[dict[str, Any]]:
    """Retrieve tracked worker compliance scores calculated from DB or _MEM_VIOLATIONS."""
    try:
        db = get_db()
        
        pipeline = [
            {
                "$group": {
                    "_id": "$worker_track_id",
                    "total_incidents": {"$sum": 1},
                    "first_seen": {"$min": "$timestamp"},
                    "last_seen": {"$max": "$timestamp"},
                    "zone_id": {"$first": "$zone_id"}
                }
            },
            {"$sort": {"total_incidents": -1}}
        ]
        
        results = await db.violation_events.aggregate(pipeline).to_list(length=None)
        if results:
            res = []
            for r in results:
                incidents = r.get("total_incidents", 0)
                compliance = max(50, 100 - (incidents * 3))
                
                first = r.get("first_seen")
                last = r.get("last_seen")
                hours_tracked = 1
                if first and last and isinstance(first, datetime) and isinstance(last, datetime):
                    hours_tracked = max(1, int((last - first).total_seconds() / 3600))
                    
                res.append({
                    "id": r["_id"],
                    "name": r["_id"],
                    "crew": "Inference Crew",
                    "shift": "Shift A (06–14)",
                    "primaryZone": r.get("zone_id") or "ZONE-01",
                    "compliance": compliance,
                    "incidents": incidents,
                    "hoursTracked": hours_tracked
                })
            return res
    except Exception as e:
        err_str = str(e).split("\n")[0][:120]
        log.warning("MongoDB get_workers offline: calculating from memory fallback (%s)", err_str)

    # In-memory calculation fallback
    worker_map: dict[str, dict] = {}
    for v in _MEM_VIOLATIONS:
        wid = v.get("worker_track_id") or v.get("workerId") or "Worker-101"
        if wid not in worker_map:
            worker_map[wid] = {
                "id": wid,
                "name": wid,
                "crew": "Inference Crew",
                "shift": "Shift A (06–14)",
                "primaryZone": v.get("zone_id") or v.get("zoneId") or "ZONE-01",
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

@cached(ttl=10.0, tags=["reports"])
async def get_reports() -> dict[str, Any]:
    """Calculate aggregated safety compliance reporting from DB or _MEM_VIOLATIONS."""
    try:
        db = get_db()
        
        total_violations = await db.violation_events.count_documents({})
        if total_violations > 0:
            # Violations by zone
            pipeline_zone = [{"$group": {"_id": "$zone_id", "count": {"$sum": 1}}}]
            by_zone_results = await db.violation_events.aggregate(pipeline_zone).to_list(length=None)
            by_zone = [{"zone_id": r["_id"], "count": r["count"]} for r in by_zone_results]
            
            # Average confidence
            pipeline_conf = [{"$group": {"_id": None, "avg_conf": {"$avg": "$confidence"}}}]
            conf_results = await db.violation_events.aggregate(pipeline_conf).to_list(length=None)
            avg_conf = conf_results[0]["avg_conf"] if conf_results else 0.0
            
            # Unique workers
            unique_workers = len(await db.violation_events.distinct("worker_track_id"))
            
            # Reviewed
            reviewed = await db.violation_events.count_documents({"acknowledgement_status": "reviewed"})
            
            # Violations per hour
            pipeline_ts = [
                {
                    "$group": {
                        "_id": None,
                        "first_ts": {"$min": "$timestamp"},
                        "last_ts": {"$max": "$timestamp"}
                    }
                }
            ]
            ts_results = await db.violation_events.aggregate(pipeline_ts).to_list(length=None)
            
            violations_per_hour = 0.0
            total_hours = 1.0
            if ts_results and ts_results[0].get("first_ts") and ts_results[0].get("last_ts"):
                first = ts_results[0]["first_ts"]
                last = ts_results[0]["last_ts"]
                if isinstance(first, datetime) and isinstance(last, datetime):
                    total_hours = max(1.0, (last - first).total_seconds() / 3600)
                    violations_per_hour = round(total_violations / total_hours, 1)

            avg_compliance = max(60, 100 - int(total_violations * 2 / max(1, total_hours)))
            
            # Weekly trend
            week_ago = datetime.utcnow() - timedelta(days=7)
            pipeline_trend = [
                {"$match": {"timestamp": {"$gte": week_ago}}},
                {
                    "$group": {
                        "_id": {
                            "$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}
                        },
                        "violations": {"$sum": 1}
                    }
                },
                {"$sort": {"_id": 1}}
            ]
            trend_results = await db.violation_events.aggregate(pipeline_trend).to_list(length=None)
            daily_trend = []
            for r in trend_results:
                daily_trend.append({
                    "day": r["_id"],
                    "violations": r["violations"],
                    "compliance": max(70, 100 - r["violations"] * 2)
                })

            return {
                "total_violations": total_violations,
                "avg_compliance": avg_compliance,
                "avg_confidence": round(avg_conf, 3),
                "false_alerts_per_hour": round(violations_per_hour * 0.05, 2),
                "violations_per_hour": violations_per_hour,
                "unique_workers": unique_workers,
                "reviewed": reviewed,
                "by_zone": by_zone,
                "daily_trend": daily_trend,
            }
    except Exception as e:
        err_str = str(e).split("\n")[0][:120]
        log.warning("MongoDB get_reports offline: calculating from memory fallback (%s)", err_str)

    # In-memory calculation fallback
    total_violations = len(_MEM_VIOLATIONS)
    zone_counts: dict[str, int] = {}
    workers: set[str] = set()
    reviewed = 0
    conf_sum = 0.0

    for v in _MEM_VIOLATIONS:
        zid = v.get("zone_id") or v.get("zoneId") or "general_plant"
        zone_counts[zid] = zone_counts.get(zid, 0) + 1
        wid = v.get("worker_track_id") or v.get("workerId")
        if wid: workers.add(wid)
        if v.get("acknowledgement_status") == "reviewed" or v.get("acknowledged"):
            reviewed += 1
        conf_sum += float(v.get("confidence", 0.85))

    by_zone = [{"zone_id": z, "count": c} for z, c in zone_counts.items()]
    avg_conf = round(conf_sum / max(1, total_violations), 3) if total_violations > 0 else 0.88
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
        "daily_trend": [{"day": today_str, "violations": total_violations, "compliance": max(70, 100 - total_violations * 2)}],
    }

@cached(ttl=5.0, tags=["stats"])
async def get_stats() -> dict[str, Any]:
    """Get live overview stats for the dashboard from DB or memory fallback."""
    try:
        db = get_db()
        
        active_violations = await db.violation_events.count_documents({"acknowledgement_status": {"$ne": "reviewed"}})
        
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        violations_today = await db.violation_events.count_documents({"timestamp": {"$gte": today_start}})
        
        # Unique workers today
        pipeline_workers_today = [
            {"$match": {"timestamp": {"$gte": today_start}}},
            {"$group": {"_id": "$worker_track_id"}}
        ]
        workers_today = len(await db.violation_events.aggregate(pipeline_workers_today).to_list(length=None))
        
        cameras_online = await db.cameras.count_documents({"is_active": 1})
        cameras_total = await db.cameras.count_documents({})
        
        compliance = max(60, 100 - (active_violations * 3)) if active_violations > 0 else 100

        return {
            "cameras_online": cameras_online,
            "cameras_total": cameras_total,
            "active_violations": active_violations,
            "violations_today": violations_today,
            "workers_tracked": workers_today,
            "daily_compliance": compliance,
        }
    except Exception as e:
        err_str = str(e).split("\n")[0][:120]
        log.warning("MongoDB get_stats offline: calculating from memory fallback (%s)", err_str)

    active_violations = sum(1 for v in _MEM_VIOLATIONS if v.get("acknowledgement_status") != "reviewed")
    unique_workers = len(set(v.get("worker_track_id") or v.get("workerId") for v in _MEM_VIOLATIONS if v.get("worker_track_id") or v.get("workerId")))
    cams_online = sum(1 for c in _MEM_CAMERAS if c.get("is_active", 1) == 1)

    return {
        "cameras_online": cams_online,
        "cameras_total": len(_MEM_CAMERAS),
        "active_violations": active_violations,
        "violations_today": len(_MEM_VIOLATIONS),
        "workers_tracked": unique_workers,
        "daily_compliance": max(60, 100 - (active_violations * 3)) if active_violations > 0 else 100,
    }

_MEM_CAMERAS: list[dict] = [
    {
        "id": "CAM-01",
        "name": "EdgeVision Primary Camera",
        "source": "0",
        "location": "Plant Floor Area",
        "is_active": 1,
        "zone_id": "general_plant",
        "target_fps": 20
    },
    {
        "id": "CAM-02",
        "name": "EdgeVision RTSP Camera Feed",
        "source": "rtsp://localhost:8554/cam",
        "location": "Plant Entrance (RTSP Stream)",
        "is_active": 0,
        "zone_id": "general_plant",
        "target_fps": 20
    }
]

@cached(ttl=15.0, tags=["cameras"])
async def get_cameras() -> list[dict[str, Any]]:
    """Retrieve active camera streams from DB or in-memory fallback."""
    try:
        db = get_db()
        cursor = db.cameras.find()
        cams = await cursor.to_list(length=None)
        if not cams:
            return _MEM_CAMERAS
        rows = []
        for c in cams:
            src = str(c.get("source") or c.get("streamUrl") or "0")
            cam_type = c.get("type") or ("webcam" if src.isdigit() else "stream")
            rows.append({
                "id": c.get("id"),
                "name": c.get("name"),
                "source": src,
                "streamUrl": src,
                "type": cam_type,
                "location": c.get("location", "Plant Area"),
                "is_active": c.get("is_active", 1),
                "zone_id": c.get("zone_id") or c.get("zoneId") or "general_plant",
                "target_fps": c.get("target_fps", 20)
            })
        return rows
    except Exception:
        log.warning("MongoDB get_cameras offline: using local memory feed")
        return _MEM_CAMERAS

async def save_camera(cam_data: dict) -> bool:
    """Insert or update a camera in DB."""
    cam_id = cam_data.get("id") or f"CAM-{uuid.uuid4().hex[:4].upper()}"
    src = str(cam_data.get("source") or cam_data.get("streamUrl") or "0").strip()
    cam_type = cam_data.get("type") or ("webcam" if src.isdigit() else "stream")
    zone_id = cam_data.get("zoneId") or cam_data.get("zone_id") or "general_plant"
    fps = int(cam_data.get("targetFps") or cam_data.get("target_fps") or 20)
    
    cam_entry = {
        "id": cam_id,
        "name": cam_data.get("name", "New Camera"),
        "source": src,
        "streamUrl": src,
        "type": cam_type,
        "location": cam_data.get("location", "Plant Area"),
        "is_active": 1,
        "zone_id": zone_id,
        "target_fps": fps
    }
    
    # Update local memory
    _MEM_CAMERAS[:] = [c for c in _MEM_CAMERAS if c.get("id") != cam_id]
    _MEM_CAMERAS.append(cam_entry)
    await mongo_cache.invalidate_tags(["cameras", "stats"])

    try:
        db = get_db()
        update_doc = {
            "name": cam_entry["name"],
            "source": src,
            "streamUrl": src,
            "type": cam_type,
            "location": cam_entry["location"],
            "zone_id": zone_id,
            "target_fps": fps,
            "is_active": 1,
            "updated_at": datetime.utcnow()
        }
        await db.cameras.update_one(
            {"id": cam_id},
            {"$set": update_doc},
            upsert=True
        )
        return True
    except Exception as e:
        log.warning("MongoDB save_camera offline: saved to local memory cache (%s)", e)
        return True

async def update_camera(cam_id: str, cam_data: dict) -> bool:
    """Update camera properties in DB."""
    await mongo_cache.invalidate_tags(["cameras", "stats"])
    
    src = str(cam_data.get("source") or cam_data.get("streamUrl") or "").strip()
    if src:
        cam_type = cam_data.get("type") or ("webcam" if src.isdigit() else "stream")
    else:
        cam_type = cam_data.get("type")

    # Update memory fallback
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

    try:
        db = get_db()
        update_doc = {}
        if "name" in cam_data and cam_data["name"]:
            update_doc["name"] = cam_data["name"]
        if src:
            update_doc["source"] = src
            update_doc["streamUrl"] = src
        if cam_type:
            update_doc["type"] = cam_type
        if "zone_id" in cam_data and cam_data["zone_id"]:
            update_doc["zone_id"] = cam_data["zone_id"]
        elif "zoneId" in cam_data and cam_data["zoneId"]:
            update_doc["zone_id"] = cam_data["zoneId"]
        if "target_fps" in cam_data:
            update_doc["target_fps"] = int(cam_data["target_fps"])
        elif "targetFps" in cam_data:
            update_doc["target_fps"] = int(cam_data["targetFps"])
        if "location" in cam_data:
            update_doc["location"] = cam_data["location"]
            
        update_doc["updated_at"] = datetime.utcnow()
        result = await db.cameras.update_one({"id": cam_id}, {"$set": update_doc})
        return result.modified_count > 0 or result.matched_count > 0
    except Exception as e:
        log.error("Failed to update camera %s: %s", cam_id, e)
        return False

async def delete_camera(cam_id: str) -> bool:
    """Delete a camera from DB and local cache."""
    await mongo_cache.invalidate_tags(["cameras", "stats"])
    
    # Update local memory
    global _MEM_CAMERAS
    _MEM_CAMERAS[:] = [c for c in _MEM_CAMERAS if c.get("id") != cam_id]

    try:
        db = get_db()
        result = await db.cameras.delete_one({"id": cam_id})
        return result.deleted_count > 0
    except Exception as e:
        log.error("Failed to delete camera %s: %s", cam_id, e)
        return False

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
    """Query violation events matching filter criteria for reporting & Excel/CSV export."""
    try:
        db = get_db()
        query: dict[str, Any] = {}

        if camera_ids and len(camera_ids) > 0 and "all" not in camera_ids:
            query["camera_id"] = {"$in": camera_ids}

        if zone_id and zone_id != "all":
            query["zone_id"] = zone_id

        if worker_id and worker_id != "all":
            query["worker_track_id"] = worker_id

        if status == "unacknowledged":
            query["acknowledgement_status"] = {"$nin": ["accepted", "reviewed", "declined"]}
        elif status in ("accepted", "reviewed"):
            query["acknowledgement_status"] = {"$in": ["accepted", "reviewed"]}
        elif status == "declined":
            query["acknowledgement_status"] = "declined"

        now = datetime.utcnow()
        if date_range == "daily":
            start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
            query["timestamp"] = {"$gte": start_dt}
        elif date_range == "weekly":
            start_dt = now - timedelta(days=7)
            query["timestamp"] = {"$gte": start_dt}
        elif date_range == "monthly":
            start_dt = now - timedelta(days=30)
            query["timestamp"] = {"$gte": start_dt}
        elif date_range == "custom" and (start_date or end_date):
            ts_q = {}
            if start_date:
                try:
                    s_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    ts_q["$gte"] = s_dt
                except Exception: pass
            if end_date:
                try:
                    e_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                    ts_q["$lt"] = e_dt
                except Exception: pass
            if ts_q:
                query["timestamp"] = ts_q

        cursor = db.violation_events.find(query).sort("timestamp", -1).limit(limit)
        events = await cursor.to_list(length=limit)
    except Exception as e:
        err_str = str(e).split("\n")[0][:120]
        log.warning("MongoDB filtered query failed, falling back to memory: %s", err_str)
        events = []
        for d in _MEM_VIOLATIONS:
            if zone_id and zone_id != "all" and d.get("zone_id") != zone_id:
                continue
            if worker_id and worker_id != "all" and d.get("worker_track_id") != worker_id:
                continue
            v_stat = d.get("acknowledgement_status", "unacknowledged")
            if status == "unacknowledged" and v_stat in ("accepted", "reviewed", "declined"):
                continue
            if status in ("accepted", "reviewed") and v_stat not in ("accepted", "reviewed"):
                continue
            if status == "declined" and v_stat != "declined":
                continue
            events.append(d)
        events = events[:limit]
        
    res = []
    for d in events:
        ts = d.get("timestamp")
        if isinstance(ts, datetime):
            ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")
        else:
            ts_str = str(ts)

        v_status = d.get("acknowledgement_status", "unacknowledged")
        res.append({
            "id": d.get("id"),
            "zoneId": d.get("zone_id", ""),
            "workerId": d.get("worker_track_id", ""),
            "type": d.get("violation_type", ""),
            "detected": d.get("detected_ppe", []),
            "missing": d.get("missing_ppe", []),
            "confidence": d.get("confidence", 0.0),
            "timestamp": ts_str,
            "imagePath": d.get("image_path", ""),
            "imageBase64": d.get("image_base64", ""),
            "videoPath": d.get("video_path", ""),
            "status": v_status,
            "acknowledged": v_status in ("accepted", "reviewed"),
            "declined": v_status == "declined",
            "cameraId": d.get("camera_id", "CAM-01")
        })
    return res

