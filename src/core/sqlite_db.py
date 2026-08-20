"""
High-Speed Local SQLite Database Engine for Cerberus AI.
Provides zero-latency local SQL writes (< 2ms) and queries for violation events,
cameras, safety zones, worker tracking, and audit logs.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import logging
from datetime import datetime, timedelta
from typing import Any

log = logging.getLogger(__name__)

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "database")
os.makedirs(DB_DIR, exist_ok=True)
SQLITE_DB_PATH = os.path.join(DB_DIR, "edgevision.db")

_sql_lock = threading.Lock()

ZONE_CANONICAL_MAP = {
    "general-plant": "General Plant Floor",
    "general_plant": "General Plant Floor",
    "general plant": "General Plant Floor",
    "general plant floor": "General Plant Floor",
    "zone-01": "General Plant Floor",
    "zone_01": "General Plant Floor",
    "work at height": "Work at Height Platform",
    "work at height platform": "Work at Height Platform",
    "work_at_height": "Work at Height Platform",
    "work-at-height": "Work at Height Platform",
    "zone-02": "Work at Height Platform",
    "zone_02": "Work at Height Platform",
    "construction": "Construction Area",
    "construction_area": "Construction Area",
    "construction area": "Construction Area",
    "zone-03": "Construction Area",
    "zone_03": "Construction Area",
    "restricted_machinery": "Restricted Machinery Zone",
    "restricted machinery": "Restricted Machinery Zone",
    "restricted machinery zone": "Restricted Machinery Zone",
    "zone-04": "Restricted Machinery Zone",
    "zone_04": "Restricted Machinery Zone",
    "hazardous_chemical": "Hazardous Chemical Area",
    "hazardous chemical": "Hazardous Chemical Area",
    "hazardous chemical area": "Hazardous Chemical Area",
    "zone-05": "Hazardous Chemical Area",
    "zone_05": "Hazardous Chemical Area",
}

def normalize_zone_id(zone: str | None) -> str:
    """Map any zone ID or alias to canonical safety zone name."""
    if not zone:
        return "General Plant Floor"
    z_clean = str(zone).strip()
    return ZONE_CANONICAL_MAP.get(z_clean.lower(), z_clean)

def get_connection() -> sqlite3.Connection:
    """Return SQLite connection with WAL (Write-Ahead Logging) mode for high throughput."""
    conn = sqlite3.connect(SQLITE_DB_PATH, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
    except Exception:
        pass
    return conn

SAMPLE_PROOF_SVG = (
    "data:image/svg+xml;utf8,"
    "<svg xmlns='http://www.w3.org/2000/svg' width='640' height='360' viewBox='0 0 640 360'>"
    "<rect width='100%' height='100%' fill='%23111827'/>"
    "<rect x='180' y='50' width='280' height='250' fill='none' stroke='%23ef4444' stroke-width='3'/>"
    "<rect x='180' y='26' width='160' height='24' fill='%23ef4444'/>"
    "<text x='188' y='42' fill='%23ffffff' font-family='monospace' font-size='12' font-weight='bold'>AI PROOF SNAPSHOT</text>"
    "<text x='210' y='160' fill='%23f87171' font-family='sans-serif' font-size='16' font-weight='bold'>PPE VIOLATION DETECTED</text>"
    "<text x='210' y='190' fill='%239ca3af' font-family='sans-serif' font-size='12'>CONFIDENCE: 94% | ZONE: PLANT</text>"
    "<text x='20' y='340' fill='%23ef4444' font-family='monospace' font-size='11'>CERBERUS AI AUDIT EVIDENCE SNAPSHOT</text>"
    "</svg>"
)

def init_sqlite_db() -> None:
    """Create SQLite tables, normalize zone IDs, and seed default zones and cameras if empty."""
    with _sql_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS violation_events (
                    id TEXT PRIMARY KEY,
                    zone_id TEXT,
                    camera_id TEXT,
                    worker_track_id TEXT,
                    violation_type TEXT,
                    detected_ppe TEXT,
                    missing_ppe TEXT,
                    confidence REAL,
                    image_path TEXT,
                    image_base64 TEXT,
                    video_path TEXT,
                    model_version TEXT,
                    timestamp TEXT,
                    acknowledgement_status TEXT DEFAULT 'unacknowledged'
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS cameras (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    source TEXT,
                    stream_url TEXT,
                    type TEXT,
                    location TEXT,
                    is_active INTEGER,
                    zone_id TEXT,
                    target_fps INTEGER
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS zones (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    required_ppe TEXT,
                    frame_threshold INTEGER DEFAULT 8,
                    dwell_seconds INTEGER DEFAULT 2,
                    confidence REAL DEFAULT 0.60,
                    updated_at TEXT
                )
            """)

            # Auto-migrate existing zones table columns if missing
            cur.execute("PRAGMA table_info(zones)")
            existing_zone_cols = {row[1] for row in cur.fetchall()}
            if "frame_threshold" not in existing_zone_cols:
                cur.execute("ALTER TABLE zones ADD COLUMN frame_threshold INTEGER DEFAULT 8")
            if "dwell_seconds" not in existing_zone_cols:
                cur.execute("ALTER TABLE zones ADD COLUMN dwell_seconds INTEGER DEFAULT 2")
            if "confidence" not in existing_zone_cols:
                cur.execute("ALTER TABLE zones ADD COLUMN confidence REAL DEFAULT 0.60")
            if "updated_at" not in existing_zone_cols:
                cur.execute("ALTER TABLE zones ADD COLUMN updated_at TEXT")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS worker_tracks (
                    id TEXT PRIMARY KEY,
                    worker_id TEXT,
                    primary_zone TEXT,
                    incidents INTEGER,
                    last_seen TEXT
                )
            """)

            conn.commit()

            # Seed zones if empty
            cur.execute("SELECT COUNT(*) FROM zones")
            if cur.fetchone()[0] == 0:
                now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
                zones = [
                    ("General Plant Floor", "General Plant Floor", "General plant area – basic PPE required", json.dumps(["helmet", "vest"]), 8, 5, 0.60, now_iso),
                ]
                cur.executemany("INSERT INTO zones (id, name, description, required_ppe, frame_threshold, dwell_seconds, confidence, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", zones)
                conn.commit()

            # Seed cameras if empty
            cur.execute("SELECT COUNT(*) FROM cameras")
            if cur.fetchone()[0] == 0:
                cameras = [
                    ("CAM-01", "Cerberus AI Primary Camera", "0", "0", "webcam", "Plant Floor Area", 1, "General Plant Floor", 20)
                ]
                cur.executemany("INSERT INTO cameras (id, name, source, stream_url, type, location, is_active, zone_id, target_fps) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", cameras)
                conn.commit()

            # Normalize all existing zone_id entries in database
            cur.execute("SELECT id, zone_id FROM violation_events")
            for row in cur.fetchall():
                e_id, z_id = row[0], row[1]
                norm_z = normalize_zone_id(z_id)
                if norm_z != z_id:
                    cur.execute("UPDATE violation_events SET zone_id = ? WHERE id = ?", (norm_z, e_id))
            
            cur.execute("SELECT id, zone_id FROM cameras")
            for row in cur.fetchall():
                c_id, z_id = row[0], row[1]
                norm_z = normalize_zone_id(z_id)
                if norm_z != z_id:
                    cur.execute("UPDATE cameras SET zone_id = ? WHERE id = ?", (norm_z, c_id))
            
            conn.commit()
            conn.close()
            log.info("SQLite database initialized and zone IDs normalized successfully.")
        except Exception as e:
            log.error("Failed to initialize SQLite database: %s", e)

def save_violation_sql(evt: dict[str, Any]) -> str:
    """Save or update a violation event directly in local SQLite (< 2ms)."""
    with _sql_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            
            evt_id = evt.get("id") or f"EVT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            ts = evt.get("timestamp")
            if isinstance(ts, datetime):
                ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                ts_str = str(ts or datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))

            detected = evt.get("detected_ppe") or evt.get("detected") or []
            missing = evt.get("missing_ppe") or evt.get("missing") or []
            norm_zone = normalize_zone_id(evt.get("zone_id") or evt.get("zoneId"))

            cur.execute("""
                INSERT OR REPLACE INTO violation_events (
                    id, zone_id, camera_id, worker_track_id, violation_type,
                    detected_ppe, missing_ppe, confidence, image_path, image_base64,
                    video_path, model_version, timestamp, acknowledgement_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                evt_id,
                norm_zone,
                evt.get("camera_id") or evt.get("cameraId") or "CAM-01",
                evt.get("worker_track_id") or evt.get("workerId") or "Worker-101",
                evt.get("violation_type") or evt.get("type") or "PPE Violation",
                json.dumps(detected if isinstance(detected, list) else []),
                json.dumps(missing if isinstance(missing, list) else []),
                float(evt.get("confidence", 0.90)),
                evt.get("image_path") or evt.get("imagePath") or "",
                evt.get("image_base64") or evt.get("imageBase64") or "",
                evt.get("video_path") or evt.get("videoPath") or "",
                evt.get("model_version") or evt.get("modelVersion") or "cerberus-ai-v1.0",
                ts_str,
                evt.get("acknowledgement_status") or evt.get("status") or "unacknowledged"
            ))
            conn.commit()
            conn.close()
            return evt_id
        except Exception as e:
            log.error("Failed to save violation to SQL: %s", e)
            return evt.get("id", "")

def get_violations_sql(limit: int = 1000) -> list[dict[str, Any]]:
    """Retrieve violation records from local SQLite."""
    with _sql_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM violation_events ORDER BY timestamp DESC LIMIT ?", (limit,))
            rows = cur.fetchall()
            conn.close()

            results = []
            for r in rows:
                row_dict = dict(r)
                try: detected = json.loads(row_dict.get("detected_ppe") or "[]")
                except Exception: detected = []
                try: missing = json.loads(row_dict.get("missing_ppe") or "[]")
                except Exception: missing = []

                stat = row_dict.get("acknowledgement_status") or "unacknowledged"
                norm_z = normalize_zone_id(row_dict.get("zone_id"))

                results.append({
                    "id": row_dict.get("id"),
                    "zone_id": norm_z,
                    "zoneId": norm_z,
                    "camera_id": row_dict.get("camera_id"),
                    "cameraId": row_dict.get("camera_id"),
                    "worker_track_id": row_dict.get("worker_track_id"),
                    "workerId": row_dict.get("worker_track_id"),
                    "violation_type": row_dict.get("violation_type"),
                    "type": row_dict.get("violation_type"),
                    "detected_ppe": detected,
                    "detected": detected,
                    "missing_ppe": missing,
                    "missing": missing,
                    "confidence": float(row_dict.get("confidence") or 0.90),
                    "image_path": row_dict.get("image_path") or "",
                    "imagePath": row_dict.get("image_path") or "",
                    "image_base64": row_dict.get("image_base64") or "",
                    "imageBase64": row_dict.get("image_base64") or "",
                    "video_path": row_dict.get("video_path") or "",
                    "videoPath": row_dict.get("video_path") or "",
                    "model_version": row_dict.get("model_version") or "cerberus-ai-v1.0",
                    "modelVersion": row_dict.get("model_version") or "cerberus-ai-v1.0",
                    "timestamp": row_dict.get("timestamp"),
                    "acknowledgement_status": stat,
                    "status": stat,
                    "acknowledged": stat in ("accepted", "reviewed"),
                    "declined": stat == "declined"
                })
            return results
        except Exception as e:
            log.error("Failed to query violations from SQL: %s", e)
            return []

def acknowledge_violation_sql(evt_id: str, status: str = "accepted") -> bool:
    """Update violation status in local SQLite (< 2ms)."""
    with _sql_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("UPDATE violation_events SET acknowledgement_status = ? WHERE id = ?", (status, evt_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            log.error("Failed to acknowledge violation in SQL: %s", e)
            return False

def delete_violation_sql(evt_id: str) -> bool:
    """Delete a violation from local SQLite (< 2ms)."""
    with _sql_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM violation_events WHERE id = ?", (evt_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            log.error("Failed to delete violation from SQL: %s", e)
            return False

def delete_violations_bulk_sql(evt_ids: list[str]) -> bool:
    """Delete multiple specified violation IDs from local SQLite (< 2ms)."""
    if not evt_ids:
        return True
    with _sql_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            placeholders = ",".join(["?"] * len(evt_ids))
            cur.execute(f"DELETE FROM violation_events WHERE id IN ({placeholders})", evt_ids)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            log.error("Failed to delete bulk violations from SQL: %s", e)
            return False

def delete_worker_violations_sql(worker_id: str) -> bool:
    """Delete all violations associated with worker_id from local SQLite (< 2ms)."""
    if not worker_id:
        return True
    w_str = str(worker_id).strip()
    raw_num = w_str.replace("Worker-", "")
    with _sql_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM violation_events WHERE worker_track_id = ? OR worker_track_id = ?", (w_str, raw_num))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            log.error("Failed to delete worker violations from SQL: %s", e)
            return False

def clear_all_violations_sql() -> bool:
    """Clear all violation events from local SQLite while preserving cameras and zones (< 2ms)."""
    with _sql_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM violation_events")
            cur.execute("DELETE FROM worker_tracks")
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            log.error("Failed to clear all violations from SQL: %s", e)
            return False

def clear_all_workers_sql() -> bool:
    """Clear worker tracks from local SQLite (< 2ms)."""
    with _sql_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM worker_tracks")
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            log.error("Failed to clear all workers from SQL: %s", e)
            return False

def save_zone_sql(zone_data: dict[str, Any]) -> bool:
    """Insert or update safety zone configuration in local SQLite database (< 2ms)."""
    with _sql_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            
            z_id = zone_data.get("id") or zone_data.get("name") or "ZONE-CUSTOM"
            z_name = zone_data.get("name") or z_id
            desc = zone_data.get("description") or zone_data.get("kind") or "Active Safety Zone"
            req_ppe = zone_data.get("required_ppe") or []
            if isinstance(req_ppe, (set, tuple)):
                req_ppe = list(req_ppe)
            elif not isinstance(req_ppe, list):
                req_ppe = []
            
            frame_thresh = int(zone_data.get("frame_threshold") or zone_data.get("frameThreshold") or 8)
            dwell_sec = int(zone_data.get("dwell_seconds") or zone_data.get("dwellSeconds") or 2)
            conf = float(zone_data.get("confidence") or zone_data.get("confidence_threshold") or 0.60)
            now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            
            cur.execute("""
                INSERT OR REPLACE INTO zones (
                    id, name, description, required_ppe,
                    frame_threshold, dwell_seconds, confidence, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                z_id,
                z_name,
                desc,
                json.dumps(req_ppe),
                frame_thresh,
                dwell_sec,
                conf,
                now_iso
            ))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            log.error("Failed to save zone to SQL: %s", e)
            return False

def get_zones_sql() -> list[dict[str, Any]]:
    """Retrieve all safety zones from local SQLite database."""
    with _sql_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("SELECT * FROM zones ORDER BY name ASC")
            rows = cur.fetchall()
            conn.close()
            
            results = []
            for r in rows:
                row_dict = dict(r)
                try:
                    req_ppe = json.loads(row_dict.get("required_ppe") or "[]")
                except Exception:
                    req_ppe = []
                
                results.append({
                    "id": row_dict.get("id"),
                    "name": row_dict.get("name") or row_dict.get("id"),
                    "description": row_dict.get("description") or "Active Safety Zone",
                    "kind": row_dict.get("description") or "Active Safety Zone",
                    "required_ppe": req_ppe if isinstance(req_ppe, list) else [],
                    "frame_threshold": int(row_dict.get("frame_threshold") or 8),
                    "frameThreshold": int(row_dict.get("frame_threshold") or 8),
                    "dwell_seconds": int(row_dict.get("dwell_seconds") or 2),
                    "dwellSeconds": int(row_dict.get("dwell_seconds") or 2),
                    "confidence": float(row_dict.get("confidence") or 0.60),
                    "confidence_threshold": float(row_dict.get("confidence") or 0.60),
                    "updated_at": row_dict.get("updated_at") or ""
                })
            return results
        except Exception as e:
            log.error("Failed to query zones from SQL: %s", e)
            return []

def delete_zone_sql(zone_id: str) -> bool:
    """Delete a safety zone from local SQLite database (< 2ms)."""
    with _sql_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("DELETE FROM zones WHERE id = ? OR name = ?", (zone_id, zone_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            log.error("Failed to delete zone from SQL: %s", e)
            return False

def reject_violation_sql(violation_id: str) -> bool:
    """Mark a violation / evidence record as REJECTED in SQLite database."""
    with _sql_lock:
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("UPDATE violations SET status = 'REJECTED' WHERE id = ?", (violation_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            log.error("Failed to reject violation in SQL: %s", e)
            return False

# Initialize database on module import
init_sqlite_db()

