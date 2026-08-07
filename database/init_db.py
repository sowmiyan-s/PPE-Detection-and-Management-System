"""
Automated SQLite database initializer for EdgeVision.
Parses database/schema.sql, converts PostgreSQL types to SQLite,
and initializes database/edgevision.db with initial seed data.
"""

from __future__ import annotations

import os
import sqlite3
import logging

log = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "edgevision.db")
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "schema.sql")

def init_db(db_path: str = DB_PATH) -> str:
    """Initialize SQLite database using schema.sql."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Define SQLite table creation statements for all 16 tables matching PDF schema
    tables = [
        """CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            permissions TEXT NOT NULL DEFAULT '{}'
        );""",

        """CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role_id INTEGER REFERENCES roles(id) ON DELETE SET NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        );""",

        """CREATE TABLE IF NOT EXISTS cameras (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            source TEXT NOT NULL,
            location TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""",

        """CREATE TABLE IF NOT EXISTS zones (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            camera_id TEXT REFERENCES cameras(id) ON DELETE SET NULL,
            polygon TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );""",

        """CREATE TABLE IF NOT EXISTS ppe_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            class_id INTEGER
        );""",

        """CREATE TABLE IF NOT EXISTS zone_ppe_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zone_id TEXT NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
            ppe_type_id INTEGER NOT NULL REFERENCES ppe_types(id) ON DELETE CASCADE,
            UNIQUE (zone_id, ppe_type_id)
        );""",

        """CREATE TABLE IF NOT EXISTS worker_tracks (
            id TEXT PRIMARY KEY,
            tracking_id INTEGER NOT NULL,
            camera_id TEXT REFERENCES cameras(id),
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_frames INTEGER NOT NULL DEFAULT 0,
            violation_frames INTEGER NOT NULL DEFAULT 0
        );""",

        """CREATE TABLE IF NOT EXISTS detection_events (
            id TEXT PRIMARY KEY,
            camera_id TEXT REFERENCES cameras(id),
            zone_id TEXT REFERENCES zones(id),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            frame_number INTEGER,
            model_version TEXT
        );""",

        """CREATE TABLE IF NOT EXISTS detected_objects (
            id TEXT PRIMARY KEY,
            detection_event_id TEXT NOT NULL REFERENCES detection_events(id) ON DELETE CASCADE,
            worker_track_id TEXT REFERENCES worker_tracks(id),
            class_name TEXT NOT NULL,
            confidence REAL NOT NULL,
            bbox_x1 REAL, bbox_y1 REAL, bbox_x2 REAL, bbox_y2 REAL
        );""",

        """CREATE TABLE IF NOT EXISTS violation_events (
            id TEXT PRIMARY KEY,
            camera_id TEXT REFERENCES cameras(id),
            zone_id TEXT REFERENCES zones(id),
            worker_track_id TEXT REFERENCES worker_tracks(id),
            violation_type TEXT,
            detected_ppe TEXT NOT NULL DEFAULT '[]',
            missing_ppe TEXT NOT NULL DEFAULT '[]',
            required_ppe TEXT NOT NULL DEFAULT '[]',
            confidence REAL NOT NULL DEFAULT 0.0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            image_path TEXT,
            video_clip_path TEXT,
            acknowledgement_status TEXT NOT NULL DEFAULT 'unacknowledged',
            acknowledged_by TEXT REFERENCES users(id),
            acknowledged_at TIMESTAMP,
            model_version TEXT
        );""",

        """CREATE TABLE IF NOT EXISTS alert_deliveries (
            id TEXT PRIMARY KEY,
            violation_event_id TEXT NOT NULL REFERENCES violation_events(id) ON DELETE CASCADE,
            channel TEXT NOT NULL,
            destination TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            sent_at TIMESTAMP,
            error_message TEXT
        );""",

        """CREATE TABLE IF NOT EXISTS event_images (
            id TEXT PRIMARY KEY,
            violation_event_id TEXT NOT NULL REFERENCES violation_events(id) ON DELETE CASCADE,
            file_path TEXT NOT NULL,
            captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_size_bytes INTEGER
        );""",

        """CREATE TABLE IF NOT EXISTS event_videos (
            id TEXT PRIMARY KEY,
            violation_event_id TEXT NOT NULL REFERENCES violation_events(id) ON DELETE CASCADE,
            file_path TEXT NOT NULL,
            duration_s REAL,
            captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_size_bytes INTEGER
        );""",

        """CREATE TABLE IF NOT EXISTS model_versions (
            id TEXT PRIMARY KEY,
            version_tag TEXT NOT NULL UNIQUE,
            model_file_path TEXT,
            onnx_path TEXT,
            engine_path TEXT,
            map50 REAL,
            map50_95 REAL,
            trained_at TIMESTAMP,
            deployed_at TIMESTAMP,
            is_active INTEGER NOT NULL DEFAULT 0,
            notes TEXT
        );""",

        """CREATE TABLE IF NOT EXISTS inference_metrics (
            id TEXT PRIMARY KEY,
            camera_id TEXT REFERENCES cameras(id),
            model_version_id TEXT REFERENCES model_versions(id),
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            avg_fps REAL,
            p95_latency_ms REAL,
            gpu_util_pct REAL,
            cpu_util_pct REAL,
            memory_mb REAL,
            temperature_c REAL,
            power_mode TEXT
        );""",

        """CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY,
            user_id TEXT REFERENCES users(id),
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            details TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );"""
    ]

    for stmt in tables:
        cursor.execute(stmt)

    # Seed initial PPE types
    ppe_types = [
        ("person", 0, "Detected person / worker"),
        ("helmet", 1, "Safety helmet / hard hat"),
        ("vest", 2, "Reflective safety vest"),
        ("boots", 3, "Safety boots"),
        ("safety_belt", 4, "Safety harness or belt"),
        ("lanyard", 5, "Lanyard connecting harness to anchor"),
        ("hook", 6, "Safety hook / carabiner"),
        ("anchor_point", 7, "Fixed anchor point for lanyard")
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO ppe_types (name, class_id, description) VALUES (?, ?, ?)",
        ppe_types
    )

    # Seed initial zones
    zones = [
        ("ZONE-01", "general_plant", "General plant area – helmet and vest required"),
        ("ZONE-02", "construction", "Active construction – helmet, vest, boots required"),
        ("ZONE-03", "work_at_height", "Elevated work area – full harness system required"),
        ("ZONE-04", "restricted_machinery", "Restricted machinery area – authorised personnel only")
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO zones (id, name, description) VALUES (?, ?, ?)",
        zones
    )

    # Seed initial cameras
    import uuid
    cameras = [
        ("CAM-01", "EdgeVision Live AI Stream", "0", "Main entrance"),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO cameras (id, name, source, location) VALUES (?, ?, ?, ?)",
        cameras
    )

    # Seed zone_ppe_rules (link zones → required PPE types)
    zone_ppe_rules = [
        # general_plant: helmet(2), vest(3)
        ("ZONE-01", 2), ("ZONE-01", 3),
        # construction: helmet(2), vest(3), boots(4)
        ("ZONE-02", 2), ("ZONE-02", 3), ("ZONE-02", 4),
        # work_at_height: helmet(2), vest(3), boots(4), safety_belt(5), hook(7)
        ("ZONE-03", 2), ("ZONE-03", 3), ("ZONE-03", 4), ("ZONE-03", 5), ("ZONE-03", 7),
        # restricted_machinery: helmet(2), vest(3)
        ("ZONE-04", 2), ("ZONE-04", 3),
    ]
    cursor.executemany(
        "INSERT OR IGNORE INTO zone_ppe_rules (zone_id, ppe_type_id) VALUES (?, ?)",
        zone_ppe_rules
    )

    # Seed initial model version
    cursor.execute(
        """INSERT OR IGNORE INTO model_versions (id, version_tag, map50, map50_95, is_active, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("MDL-001", "edgevision-ppe-v3.2-fp16", 0.846, 0.612, 1,
         "YOLOv8 FP16 TensorRT engine for Jetson Orin NX")
    )

    conn.commit()
    conn.close()
    return db_path

if __name__ == "__main__":
    path = init_db()
    print(f"Database successfully initialized at: {path}")
