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
import time
from typing import Any
from datetime import datetime, timedelta

from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

from src.core import config

log = logging.getLogger(__name__)

EVIDENCE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "database", "evidence")
os.makedirs(EVIDENCE_DIR, exist_ok=True)

_client = None
_db = None

def get_db():
    """Connect to MongoDB database and return the database instance."""
    global _client, _db
    if _db is None:
        try:
            _client = MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=5000)
            _db = _client[config.MONGODB_DB_NAME]
            # Verify connection
            _client.admin.command('ping')
            log.info(f"Connected to MongoDB at {config.MONGODB_URI}")
        except ConnectionFailure as e:
            log.error(f"Failed to connect to MongoDB: {e}")
            raise
    return _db

def ensure_db():
    """Initialize database collections and seed data if they don't exist yet."""
    db = get_db()
    
    # Check if we need to seed zones
    if db.zones.count_documents({}) == 0:
        log.info("Seeding initial zones...")
        zones = [
            {"id": "ZONE-01", "name": "general_plant", "description": "General plant area – helmet and vest required", "required_ppe": ["helmet", "vest"]},
            {"id": "ZONE-02", "name": "construction", "description": "Active construction – helmet, vest, boots required", "required_ppe": ["helmet", "vest", "boots"]},
            {"id": "ZONE-03", "name": "work_at_height", "description": "Elevated work area – full harness system required", "required_ppe": ["helmet", "vest", "boots", "safety_belt", "hook"]},
            {"id": "ZONE-04", "name": "restricted_machinery", "description": "Restricted machinery area – authorised personnel only", "required_ppe": ["helmet", "vest"]}
        ]
        db.zones.insert_many(zones)

    # Check if we need to seed cameras
    if db.cameras.count_documents({}) == 0:
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
        db.cameras.insert_many(cameras)
        
    log.info("MongoDB database initialized successfully.")

def record_violation(
    worker_id: str,
    zone_id: str,
    violation_type: str,
    detected_ppe: list[str],
    missing_ppe: list[str],
    confidence: float,
    image_path: str = "",
    model_version: str = "edgevision-ppe-v3.2-fp16"
) -> str:
    """Record a violation event with image evidence into MongoDB."""
    evt_id = f"EVT-{uuid.uuid4().hex[:6].upper()}"
    try:
        db = get_db()
        event = {
            "id": evt_id,
            "zone_id": zone_id,
            "worker_track_id": worker_id,
            "violation_type": violation_type,
            "detected_ppe": detected_ppe,
            "missing_ppe": missing_ppe,
            "confidence": confidence,
            "image_path": image_path,
            "model_version": model_version,
            "timestamp": datetime.utcnow(),
            "acknowledgement_status": "unacknowledged"
        }
        db.violation_events.insert_one(event)
        log.info("Recorded violation %s for %s in zone %s", evt_id, worker_id, zone_id)
    except Exception as e:
        log.error("Failed to record violation: %s", e)
    return evt_id

def acknowledge_violation(evt_id: str) -> bool:
    """Mark a violation event as acknowledged."""
    try:
        db = get_db()
        result = db.violation_events.update_one(
            {"id": evt_id},
            {"$set": {"acknowledgement_status": "reviewed"}}
        )
        return result.modified_count > 0
    except Exception as e:
        log.error("Failed to acknowledge violation %s: %s", evt_id, e)
        return False

def get_violations(limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve recent violation events with proof of evidence."""
    try:
        db = get_db()
        events = db.violation_events.find().sort("timestamp", -1).limit(limit)
        res = []
        for d in events:
            # Format timestamp as string to be consistent with previous SQLite behavior
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
                "status": d.get("acknowledgement_status"),
                "modelVersion": d.get("model_version"),
                "acknowledged": d.get("acknowledgement_status") == "reviewed",
                "cameraId": d.get("camera_id", "CAM-01")
            })
        return res
    except Exception as e:
        log.error("Failed to fetch violations: %s", e)
        return []

def get_zones() -> list[dict[str, Any]]:
    """Retrieve configured safety zones with their required PPE."""
    try:
        db = get_db()
        zones = db.zones.find()
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

def save_zone(zone_data: dict) -> bool:
    """Insert or update safety zone configuration in DB."""
    try:
        db = get_db()
        zone_id = zone_data.get("id", f"ZONE-{uuid.uuid4().hex[:4].upper()}")
        
        update_doc = {
            "name": zone_data.get("name", "Custom Zone"),
            "description": zone_data.get("kind", zone_data.get("description", "General plant"))
        }
        if "required_ppe" in zone_data:
            update_doc["required_ppe"] = zone_data["required_ppe"]
            
        db.zones.update_one(
            {"id": zone_id},
            {"$set": update_doc},
            upsert=True
        )
        return True
    except Exception as e:
        log.error("Failed to save zone: %s", e)
        return False

def get_workers() -> list[dict[str, Any]]:
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
        
        results = db.violation_events.aggregate(pipeline)
        
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

def get_reports() -> dict[str, Any]:
    """Calculate aggregated safety compliance reporting from DB."""
    try:
        db = get_db()
        
        total_violations = db.violation_events.count_documents({})
        
        # Violations by zone
        pipeline_zone = [{"$group": {"_id": "$zone_id", "count": {"$sum": 1}}}]
        by_zone_results = db.violation_events.aggregate(pipeline_zone)
        by_zone = [{"zone_id": r["_id"], "count": r["count"]} for r in by_zone_results]
        
        # Average confidence
        pipeline_conf = [{"$group": {"_id": None, "avg_conf": {"$avg": "$confidence"}}}]
        conf_results = list(db.violation_events.aggregate(pipeline_conf))
        avg_conf = conf_results[0]["avg_conf"] if conf_results else 0.0
        
        # Unique workers
        unique_workers = len(db.violation_events.distinct("worker_track_id"))
        
        # Reviewed
        reviewed = db.violation_events.count_documents({"acknowledgement_status": "reviewed"})
        
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
        ts_results = list(db.violation_events.aggregate(pipeline_ts))
        
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
        trend_results = db.violation_events.aggregate(pipeline_trend)
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

def get_stats() -> dict[str, Any]:
    """Get live overview stats for the dashboard."""
    try:
        db = get_db()
        
        active_violations = db.violation_events.count_documents({"acknowledgement_status": {"$ne": "reviewed"}})
        
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        violations_today = db.violation_events.count_documents({"timestamp": {"$gte": today_start}})
        
        # Unique workers today
        pipeline_workers_today = [
            {"$match": {"timestamp": {"$gte": today_start}}},
            {"$group": {"_id": "$worker_track_id"}}
        ]
        workers_today = len(list(db.violation_events.aggregate(pipeline_workers_today)))
        
        cameras_online = db.cameras.count_documents({"is_active": 1})
        cameras_total = db.cameras.count_documents({})
        
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

def get_cameras() -> list[dict[str, Any]]:
    """Retrieve registered cameras from DB."""
    try:
        db = get_db()
        cameras = db.cameras.find().sort("id", 1)
        rows = []
        for c in cameras:
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
    except Exception as e:
        log.error("Failed to fetch cameras: %s", e)
        return []

def save_camera(cam_data: dict) -> bool:
    """Insert or update a camera in DB."""
    try:
        db = get_db()
        cam_id = cam_data.get("id", f"CAM-{uuid.uuid4().hex[:4].upper()}")
        
        db.cameras.update_one(
            {"id": cam_id},
            {
                "$set": {
                    "name": cam_data.get("name", "New Camera"),
                    "source": cam_data.get("source", cam_data.get("streamUrl", "0")),
                    "location": cam_data.get("location", ""),
                    "zone_id": cam_data.get("zoneId", "ZONE-01"),
                    "target_fps": cam_data.get("targetFps", 20),
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        return True
    except Exception as e:
        log.error("Failed to save camera: %s", e)
        return False
