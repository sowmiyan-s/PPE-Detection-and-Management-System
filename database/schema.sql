-- EdgeVision Industrial PPE and Work-at-Height Safety Monitoring Platform
-- Complete PostgreSQL Relational Database Schema
-- Version: 1.0.0

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Roles Table
CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Users Table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role_id INT REFERENCES roles(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Cameras Table
CREATE TABLE IF NOT EXISTS cameras (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    rtsp_url VARCHAR(500) NOT NULL,
    location VARCHAR(200),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'maintenance', 'error')),
    fps INT DEFAULT 20,
    resolution VARCHAR(20) DEFAULT '1920x1080',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Zones Table
CREATE TABLE IF NOT EXISTS zones (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    polygon_coords JSONB, -- JSON array of [x, y] coordinates normalized
    height_threshold_meters NUMERIC(5, 2) DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. PPE Types Table
CREATE TABLE IF NOT EXISTS ppe_types (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL, -- e.g. helmet, vest, boots, harness, lanyard, hook
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_mandatory_default BOOLEAN DEFAULT FALSE
);

-- 6. Zone PPE Rules Table
CREATE TABLE IF NOT EXISTS zone_ppe_rules (
    id SERIAL PRIMARY KEY,
    zone_id VARCHAR(50) REFERENCES zones(id) ON DELETE CASCADE,
    ppe_type_id INT REFERENCES ppe_types(id) ON DELETE CASCADE,
    is_required BOOLEAN DEFAULT TRUE,
    requires_authorization BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(zone_id, ppe_type_id)
);

-- 7. Model Versions Table
CREATE TABLE IF NOT EXISTS model_versions (
    id VARCHAR(50) PRIMARY KEY, -- e.g. v1.0.0
    name VARCHAR(100) NOT NULL,
    framework VARCHAR(50) DEFAULT 'TensorRT',
    precision VARCHAR(20) DEFAULT 'FP16',
    map50 NUMERIC(5, 4),
    map50_95 NUMERIC(5, 4),
    file_path VARCHAR(500),
    deployed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT FALSE
);

-- 8. Worker Tracks Table
CREATE TABLE IF NOT EXISTS worker_tracks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tracking_id INT NOT NULL,
    camera_id VARCHAR(50) REFERENCES cameras(id) ON DELETE CASCADE,
    zone_id VARCHAR(50) REFERENCES zones(id) ON DELETE SET NULL,
    first_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_authorized BOOLEAN DEFAULT FALSE
);

-- 9. Detection Events Table
CREATE TABLE IF NOT EXISTS detection_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id VARCHAR(50) REFERENCES cameras(id) ON DELETE CASCADE,
    zone_id VARCHAR(50) REFERENCES zones(id) ON DELETE SET NULL,
    worker_track_id UUID REFERENCES worker_tracks(id) ON DELETE SET NULL,
    worker_tracking_id INT,
    model_version VARCHAR(50) REFERENCES model_versions(id) ON DELETE SET NULL,
    frame_number BIGINT,
    confidence NUMERIC(4, 3),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 10. Detected Objects Table
CREATE TABLE IF NOT EXISTS detected_objects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    detection_event_id UUID REFERENCES detection_events(id) ON DELETE CASCADE,
    class_name VARCHAR(50) NOT NULL,
    confidence NUMERIC(4, 3) NOT NULL,
    bbox JSONB NOT NULL, -- [x1, y1, x2, y2]
    associated_worker_id INT
);

-- 11. Violation Events Table
CREATE TABLE IF NOT EXISTS violation_events (
    id VARCHAR(100) PRIMARY KEY, -- e.g. VIOL-20260816-0001
    camera_id VARCHAR(50) REFERENCES cameras(id) ON DELETE CASCADE,
    zone_id VARCHAR(50) REFERENCES zones(id) ON DELETE SET NULL,
    worker_tracking_id INT NOT NULL,
    violation_type VARCHAR(100) NOT NULL, -- e.g. missing_helmet, unhooked_harness
    detected_ppe TEXT[], -- Array of present PPE classes
    missing_ppe TEXT[],  -- Array of required but absent PPE classes
    confidence NUMERIC(4, 3) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    acknowledgement_status VARCHAR(20) DEFAULT 'unacknowledged' CHECK (acknowledgement_status IN ('unacknowledged', 'acknowledged', 'resolved', 'false_positive')),
    acknowledged_by UUID REFERENCES users(id) ON DELETE SET NULL,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    model_version VARCHAR(50) REFERENCES model_versions(id) ON DELETE SET NULL
);

-- 12. Event Images Table
CREATE TABLE IF NOT EXISTS event_images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    violation_event_id VARCHAR(100) REFERENCES violation_events(id) ON DELETE CASCADE,
    image_url VARCHAR(500) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 13. Event Videos Table
CREATE TABLE IF NOT EXISTS event_videos (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    violation_event_id VARCHAR(100) REFERENCES violation_events(id) ON DELETE CASCADE,
    video_url VARCHAR(500) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    duration_seconds NUMERIC(5, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 14. Alert Deliveries Table
CREATE TABLE IF NOT EXISTS alert_deliveries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    violation_event_id VARCHAR(100) REFERENCES violation_events(id) ON DELETE CASCADE,
    channel VARCHAR(50) NOT NULL CHECK (channel IN ('mqtt', 'email', 'webhook', 'sms')),
    recipient VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'sent' CHECK (status IN ('pending', 'sent', 'failed')),
    sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT
);

-- 15. Inference Metrics Table
CREATE TABLE IF NOT EXISTS inference_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    camera_id VARCHAR(50) REFERENCES cameras(id) ON DELETE CASCADE,
    fps NUMERIC(5, 2) NOT NULL,
    p95_latency_ms NUMERIC(6, 2) NOT NULL,
    cpu_usage_pct NUMERIC(5, 2),
    gpu_usage_pct NUMERIC(5, 2),
    memory_usage_mb NUMERIC(7, 2),
    temperature_c NUMERIC(4, 1),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 16. Audit Logs Table
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(100) NOT NULL,
    details JSONB,
    ip_address VARCHAR(45),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for Fast Query Performance
CREATE INDEX IF NOT EXISTS idx_violation_events_timestamp ON violation_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_violation_events_camera_zone ON violation_events(camera_id, zone_id);
CREATE INDEX IF NOT EXISTS idx_violation_events_status ON violation_events(acknowledgement_status);
CREATE INDEX IF NOT EXISTS idx_worker_tracks_camera ON worker_tracks(camera_id, tracking_id);
CREATE INDEX IF NOT EXISTS idx_inference_metrics_timestamp ON inference_metrics(timestamp DESC);

-- Seed Default Roles
INSERT INTO roles (name, description) VALUES
    ('admin', 'Full system administration and user management'),
    ('operator', 'View dashboard, acknowledge violations, and manage cameras'),
    ('auditor', 'Read-only access for safety compliance auditing')
ON CONFLICT (name) DO NOTHING;

-- Seed Default PPE Types
INSERT INTO ppe_types (code, name, description, is_mandatory_default) VALUES
    ('helmet', 'Safety Helmet', 'Hard hat protective headwear', TRUE),
    ('vest', 'Reflective Safety Vest', 'High-visibility safety vest', TRUE),
    ('boots', 'Safety Boots', 'Steel-toe protective footwear', FALSE),
    ('gloves', 'Safety Gloves', 'Protective handwear', FALSE),
    ('glasses', 'Safety Glasses', 'Eye protection glasses', FALSE),
    ('mask', 'Face Mask', 'Protective respiratory mask', FALSE),
    ('earmuffs', 'Ear Protection', 'Hearing protection earmuffs', FALSE)
ON CONFLICT (code) DO NOTHING;

-- Seed Default Zones
INSERT INTO zones (id, name, description, height_threshold_meters) VALUES
    ('general_plant', 'General Plant Floor', 'Main operational plant area – basic PPE required', 0.0)
ON CONFLICT (id) DO NOTHING;

-- Seed Default Model Version
INSERT INTO model_versions (id, name, framework, precision, map50, map50_95, file_path, is_active) VALUES
    ('v1.0.0', 'EdgeVision YOLOv8 PPE Detector', 'TensorRT', 'FP16', 0.8850, 0.6420, 'models/best.engine', TRUE)
ON CONFLICT (id) DO NOTHING;
