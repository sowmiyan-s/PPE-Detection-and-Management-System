-- EdgeVision PPE Compliance Platform – PostgreSQL Schema
-- Run: psql -U ppe_user -d ppe_db -f database/schema.sql
-- See database/migrations/ for incremental updates.

BEGIN;

-- ── Extensions ──────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- for fast text search on event fields

-- ── Roles / Users ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS roles (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(64)  NOT NULL UNIQUE,  -- admin, operator, viewer
    permissions JSONB        NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS users (
    id           UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    username     VARCHAR(128) NOT NULL UNIQUE,
    email        VARCHAR(256) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role_id      INTEGER      REFERENCES roles(id) ON DELETE SET NULL,
    is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_login   TIMESTAMPTZ
);

-- ── Cameras ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cameras (
    id          UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(128) NOT NULL,
    source      TEXT         NOT NULL,    -- 0, rtsp://…, /dev/videoN
    location    VARCHAR(256),
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ── Zones ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS zones (
    id          UUID         PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(128) NOT NULL UNIQUE,  -- general_plant, work_at_height …
    description TEXT,
    camera_id   UUID         REFERENCES cameras(id) ON DELETE SET NULL,
    -- Optional polygon defining the zone in pixel coordinates (JSON array of [x,y])
    polygon     JSONB,
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ── PPE types ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ppe_types (
    id          SERIAL       PRIMARY KEY,
    name        VARCHAR(64)  NOT NULL UNIQUE,  -- helmet, vest, boots …
    description TEXT,
    class_id    INTEGER                        -- YOLO class index
);

-- ── Zone → required PPE rules ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS zone_ppe_rules (
    id         SERIAL  PRIMARY KEY,
    zone_id    UUID    NOT NULL REFERENCES zones(id)     ON DELETE CASCADE,
    ppe_type_id INTEGER NOT NULL REFERENCES ppe_types(id) ON DELETE CASCADE,
    UNIQUE (zone_id, ppe_type_id)
);

-- ── Worker tracks ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS worker_tracks (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    tracking_id     INTEGER     NOT NULL,    -- ByteTrack temporary ID
    camera_id       UUID        REFERENCES cameras(id),
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_frames    INTEGER     NOT NULL DEFAULT 0,
    violation_frames INTEGER    NOT NULL DEFAULT 0,
    UNIQUE (tracking_id, camera_id)
);

-- ── Detection events (one per frame with detections) ──────────────────────────
CREATE TABLE IF NOT EXISTS detection_events (
    id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id   UUID        REFERENCES cameras(id),
    zone_id     UUID        REFERENCES zones(id),
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    frame_number BIGINT,
    model_version VARCHAR(64)
);

-- ── Detected objects (one per bounding box per frame) ─────────────────────────
CREATE TABLE IF NOT EXISTS detected_objects (
    id               UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
    detection_event_id UUID  NOT NULL REFERENCES detection_events(id) ON DELETE CASCADE,
    worker_track_id  UUID    REFERENCES worker_tracks(id),
    class_name       VARCHAR(64) NOT NULL,
    confidence       REAL    NOT NULL,
    bbox_x1          REAL,
    bbox_y1          REAL,
    bbox_x2          REAL,
    bbox_y2          REAL
);

-- ── Violation events ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS violation_events (
    id                 UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id          UUID        REFERENCES cameras(id),
    zone_id            UUID        REFERENCES zones(id),
    worker_track_id    UUID        REFERENCES worker_tracks(id),
    violation_type     VARCHAR(128),           -- e.g. "missing_helmet"
    detected_ppe       JSONB       NOT NULL DEFAULT '[]',
    missing_ppe        JSONB       NOT NULL DEFAULT '[]',
    required_ppe       JSONB       NOT NULL DEFAULT '[]',
    confidence         REAL        NOT NULL DEFAULT 0.0,
    timestamp          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    image_path         TEXT,                   -- path to evidence image
    video_clip_path    TEXT,                   -- path to evidence video clip
    acknowledgement_status VARCHAR(32) NOT NULL DEFAULT 'unacknowledged',
    acknowledged_by    UUID        REFERENCES users(id),
    acknowledged_at    TIMESTAMPTZ,
    model_version      VARCHAR(64)
);

-- ── Alert deliveries ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alert_deliveries (
    id                UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    violation_event_id UUID       NOT NULL REFERENCES violation_events(id) ON DELETE CASCADE,
    channel           VARCHAR(32) NOT NULL,    -- mqtt, email, webhook, sms
    destination       TEXT        NOT NULL,
    status            VARCHAR(32) NOT NULL DEFAULT 'pending',  -- sent, failed, pending
    sent_at           TIMESTAMPTZ,
    error_message     TEXT
);

-- ── Event images ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS event_images (
    id                UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    violation_event_id UUID       NOT NULL REFERENCES violation_events(id) ON DELETE CASCADE,
    file_path         TEXT        NOT NULL,
    captured_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    file_size_bytes   INTEGER
);

-- ── Event video clips ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS event_videos (
    id                UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    violation_event_id UUID       NOT NULL REFERENCES violation_events(id) ON DELETE CASCADE,
    file_path         TEXT        NOT NULL,
    duration_s        REAL,
    captured_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    file_size_bytes   INTEGER
);

-- ── Model versions ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS model_versions (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    version_tag     VARCHAR(64) NOT NULL UNIQUE,
    model_file_path TEXT,
    onnx_path       TEXT,
    engine_path     TEXT,
    map50           REAL,
    map50_95        REAL,
    trained_at      TIMESTAMPTZ,
    deployed_at     TIMESTAMPTZ,
    is_active       BOOLEAN     NOT NULL DEFAULT FALSE,
    notes           TEXT
);

-- ── Inference metrics (per session / per hour) ────────────────────────────────
CREATE TABLE IF NOT EXISTS inference_metrics (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id       UUID        REFERENCES cameras(id),
    model_version_id UUID       REFERENCES model_versions(id),
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    avg_fps         REAL,
    p95_latency_ms  REAL,
    gpu_util_pct    REAL,
    cpu_util_pct    REAL,
    memory_mb       REAL,
    temperature_c   REAL,
    power_mode      VARCHAR(64)
);

-- ── Audit log ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id          UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID        REFERENCES users(id),
    action      VARCHAR(128) NOT NULL,
    entity_type VARCHAR(64),
    entity_id   UUID,
    details     JSONB,
    ip_address  INET,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_violation_events_timestamp    ON violation_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_violation_events_camera       ON violation_events(camera_id);
CREATE INDEX IF NOT EXISTS idx_violation_events_zone         ON violation_events(zone_id);
CREATE INDEX IF NOT EXISTS idx_violation_events_worker       ON violation_events(worker_track_id);
CREATE INDEX IF NOT EXISTS idx_violation_events_status       ON violation_events(acknowledgement_status);
CREATE INDEX IF NOT EXISTS idx_detection_events_timestamp    ON detection_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_detected_objects_event        ON detected_objects(detection_event_id);
CREATE INDEX IF NOT EXISTS idx_worker_tracks_tracking_id     ON worker_tracks(tracking_id);
CREATE INDEX IF NOT EXISTS idx_inference_metrics_recorded_at ON inference_metrics(recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at         ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user               ON audit_logs(user_id);

-- ── Seed data ─────────────────────────────────────────────────────────────────

INSERT INTO roles (name, permissions) VALUES
    ('admin',    '{"all": true}'),
    ('operator', '{"view": true, "acknowledge": true}'),
    ('viewer',   '{"view": true}')
ON CONFLICT (name) DO NOTHING;

INSERT INTO ppe_types (name, class_id, description) VALUES
    ('person',       0, 'Detected person / worker'),
    ('helmet',       1, 'Safety helmet / hard hat'),
    ('vest',         2, 'Reflective safety vest'),
    ('boots',        3, 'Safety boots'),
    ('safety_belt',  4, 'Safety harness or belt'),
    ('lanyard',      5, 'Lanyard connecting harness to anchor'),
    ('hook',         6, 'Safety hook / carabiner'),
    ('anchor_point', 7, 'Fixed anchor point for lanyard')
ON CONFLICT (name) DO NOTHING;

INSERT INTO zones (name, description) VALUES
    ('general_plant',        'General plant area – helmet and vest required'),
    ('construction',         'Active construction – helmet, vest, boots required'),
    ('work_at_height',       'Elevated work area – full harness system required'),
    ('restricted_machinery', 'Restricted machinery area – authorised personnel only')
ON CONFLICT (name) DO NOTHING;

COMMIT;
