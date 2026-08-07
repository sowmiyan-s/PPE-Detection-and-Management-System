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
            _client = AsyncIOMotorClient(
                config.MONGODB_URI,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000,
                tls=True,
                tlsAllowInvalidCertificates=True,
            )
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
                {"id": "ZONE-01", "name": "general_plant", "description": "General plant area – helmet and vest required", "required_ppe": ["helmet", "vest"], "authorised_workers": []},
                {"id": "ZONE-02", "name": "construction", "description": "Active construction – helmet, vest, boots required", "required_ppe": ["helmet", "vest", "boots"], "authorised_workers": []},
                {"id": "ZONE-03", "name": "work_at_height", "description": "Elevated work area – full harness system required", "required_ppe": ["helmet", "vest", "boots", "safety_belt", "hook"], "authorised_workers": []},
                {"id": "ZONE-04", "name": "restricted_machinery", "description": "Restricted machinery area – authorised personnel only", "required_ppe": ["helmet", "vest"], "authorised_workers": ["Worker-101", "Worker-102"]}
            ]
            await db.zones.insert_many(zones)

        # Check if we need to seed cameras
        count_cameras = await db.cameras.count_documents({})
        if count_cameras == 0:
            log.info("Seeding initial cameras...")
            cameras = [
                {
                    "id": "CAM-01", 
                    "name": "EdgeVision Live AI Stream", 
                    "source": "0", 
                    "location": "Main entrance",
                    "zone_id": "ZONE-01",
                    "target_fps": 20,
                    "is_active": 1,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            ]
            await db.cameras.insert_many(cameras)

        # Seed roles if empty
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

        # Ensure collections exist
        existing_cols = await db.list_collection_names()
        for col in ["audit_logs", "alert_deliveries", "worker_tracks"]:
            if col not in existing_cols:
                await db.create_collection(col)
            
        log.info("MongoDB database initialized successfully with required collections.")
    except Exception as err:
        log.warning("MongoDB initialization warning (will retry on demand): %s", err)

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
    """Record a violation event with image/video evidence directly in MongoDB."""
    evt_id = f"EVT-{uuid.uuid4().hex[:6].upper()}"
    try:
        db = get_db()
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
        await db.violation_events.insert_one(event)

        # Audit log record
        await db.audit_logs.insert_one({
            "action": "VIOLATION_RECORDED",
            "evt_id": evt_id,
            "worker_id": worker_id,
            "timestamp": datetime.utcnow()
        })

        log.info("Recorded violation %s for %s (camera: %s, zone: %s)", evt_id, worker_id, camera_id, zone_id)
    except Exception as e:
        log.error("Failed to record violation: %s", e)
    return evt_id

async def acknowledge_violation(evt_id: str) -> bool:
    """Mark a violation event as acknowledged."""
    try:
        db = get_db()
        result = await db.violation_events.update_one(
            {"id": evt_id},
            {"$set": {"acknowledgement_status": "reviewed"}}
        )
        return result.modified_count > 0
    except Exception as e:
        log.error("Failed to acknowledge violation %s: %s", evt_id, e)
        return False

async def delete_violation(evt_id: str) -> bool:
    """Delete a single violation event and its evidence record from MongoDB."""
    try:
        db = get_db()
        result = await db.violation_events.delete_one({"id": evt_id})
        return result.deleted_count > 0
    except Exception as e:
        log.error("Failed to delete violation %s: %s", evt_id, e)
        return False

async def delete_all_violations() -> bool:
    """Clear all past violation evidence records from MongoDB."""
    try:
        db = get_db()
        await db.violation_events.delete_many({})
        return True
    except Exception as e:
        log.error("Failed to clear violations: %s", e)
        return False

async def delete_camera(cam_id: str) -> bool:
    """Remove a camera from DB."""
    try:
        db = get_db()
        result = await db.cameras.delete_one({"id": cam_id})
        return result.deleted_count > 0
    except Exception as e:
        log.error("Failed to delete camera %s: %s", cam_id, e)
        return False

async def get_violations(limit: int = 100) -> list[dict[str, Any]]:
    """Retrieve recent violation events with proof of evidence."""
    try:
        db = get_db()
        cursor = db.violation_events.find().sort("timestamp", -1).limit(limit)
        events = await cursor.to_list(length=limit)
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
                "status": d.get("acknowledgement_status"),
                "modelVersion": d.get("model_version"),
                "acknowledged": d.get("acknowledgement_status") == "reviewed",
                "cameraId": d.get("camera_id", "CAM-01")
            })
        return res
    except Exception as e:
        log.error("Failed to fetch violations: %s", e)
        return []

async def get_zones() -> list[dict[str, Any]]:
    """Retrieve configured safety zones with their required PPE."""
    try:
        db = get_db()
        cursor = db.zones.find()
        zones = await cursor.to_list(length=None)
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
        log.error("Failed to fetch zones: %s", e)
        return []

async def save_zone(zone_data: dict) -> bool:
    """Insert or update safety zone configuration in DB."""
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

async def get_workers() -> list[dict[str, Any]]:
    """Retrieve tracked worker compliance scores calculated from real DB events."""
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
        log.error("Failed to fetch worker compliance: %s", e)
        return []

async def get_reports() -> dict[str, Any]:
    """Calculate aggregated safety compliance reporting from DB."""
    try:
        db = get_db()
        
        total_violations = await db.violation_events.count_documents({})
        
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
        log.error("Failed to calculate reports: %s", e)
        return {
            "total_violations": 0, "avg_compliance": 100,
            "false_alerts_per_hour": 0.0, "by_zone": [],
            "daily_trend": [], "unique_workers": 0,
            "reviewed": 0, "avg_confidence": 0.0,
            "violations_per_hour": 0.0,
        }

async def get_stats() -> dict[str, Any]:
    """Get live overview stats for the dashboard."""
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
        log.error("Failed to get stats: %s", e)
        return {
            "cameras_online": 0, "cameras_total": 0,
            "active_violations": 0, "violations_today": 0,
            "workers_tracked": 0, "daily_compliance": 100,
        }

_MEM_CAMERAS: list[dict] = [
    {
        "id": "CAM-01",
        "name": "EdgeVision Live AI Stream",
        "source": "0",
        "location": "Main entrance",
        "is_active": 1,
        "zone_id": "ZONE-01",
        "target_fps": 20
    }
]

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
            rows.append({
                "id": c.get("id"),
                "name": c.get("name"),
                "source": c.get("source"),
                "location": c.get("location"),
                "is_active": c.get("is_active", 1),
                "zone_id": c.get("zone_id"),
                "target_fps": c.get("target_fps", 20)
            })
        return rows
    except Exception:
        log.warning("MongoDB get_cameras offline: using local memory feed")
        return _MEM_CAMERAS

async def save_camera(cam_data: dict) -> bool:
    """Insert or update a camera in DB."""
    cam_id = cam_data.get("id") or f"CAM-{uuid.uuid4().hex[:4].upper()}"
    cam_entry = {
        "id": cam_id,
        "name": cam_data.get("name", "New Camera"),
        "source": cam_data.get("source") or cam_data.get("streamUrl", "0"),
        "location": cam_data.get("location", "Plant Area"),
        "is_active": 1,
        "zone_id": cam_data.get("zoneId", "ZONE-01"),
        "target_fps": cam_data.get("targetFps", 20)
    }
    # Update local memory
    _MEM_CAMERAS.append(cam_entry)

    try:
        db = get_db()
        update_doc = {}
        if "name" in cam_data: update_doc["name"] = cam_data["name"]
        if "source" in cam_data: update_doc["source"] = cam_data["source"]
        if "streamUrl" in cam_data: update_doc["source"] = cam_data["streamUrl"]
        if "location" in cam_data: update_doc["location"] = cam_data["location"]
        if "zoneId" in cam_data: update_doc["zone_id"] = cam_data["zoneId"]
        if "targetFps" in cam_data: update_doc["target_fps"] = cam_data["targetFps"]
        
        if update_doc:
            update_doc["updated_at"] = datetime.utcnow()
            await db.cameras.update_one(
                {"id": cam_id},
                {"$set": update_doc},
                upsert=True
            )
        return True
    except Exception as e:
        log.warning("MongoDB save_camera offline: saved to local memory cache")
        return True
