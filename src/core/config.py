"""
Central configuration for the EdgeVision PPE Compliance Platform.
All tuneable values live here; environment variables override where relevant.
"""

import os

# ── MQTT ──────────────────────────────────────────────────────────────────────
MQTT_BROKER   = os.getenv("MQTT_BROKER", "test.mosquitto.org")
MQTT_PORT     = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC    = os.getenv("MQTT_TOPIC", "factory/ppe_violations")
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_USE_TLS  = os.getenv("MQTT_USE_TLS", "false").lower() == "true"

# ── Model ─────────────────────────────────────────────────────────────────────
DEFAULT_MODEL_PATH  = os.getenv(
    "MODEL_PATH",
    "experiments/ppe_training/custom_model/weights/best.pt"
)
FALLBACK_MODEL_PATH = "models/yolov8n.pt"
DETECTION_CONF      = float(os.getenv("DETECTION_CONF", "0.20"))
TRACKER_CONFIG      = "bytetrack.yaml"

# ── PPE classes (must match dataset.yaml order) ───────────────────────────────
PPE_CLASSES = [
    "person",
    "helmet",
    "vest",
    "boots",
    "safety_belt",
    "lanyard",
    "hook",
    "anchor_point",
]

# ── Stage-3 association ───────────────────────────────────────────────────────
PPE_CONTAINMENT_THRESHOLD = float(os.getenv("PPE_CONTAINMENT_THRESHOLD", "0.40"))

# ── Stage-5 temporal validation ───────────────────────────────────────────────
TEMPORAL_WINDOW        = int(os.getenv("TEMPORAL_WINDOW", "10"))       # frames
TEMPORAL_MIN_HITS      = int(os.getenv("TEMPORAL_MIN_HITS", "8"))      # out of WINDOW
TEMPORAL_MIN_CONF      = float(os.getenv("TEMPORAL_MIN_CONF", "0.30")) # confidence
TEMPORAL_MIN_ZONE_SECS = float(os.getenv("TEMPORAL_MIN_ZONE_SECS", "2.0"))  # seconds

# ── Zone rule engine (Stage-4) ────────────────────────────────────────────────
# Each zone maps to a set of required PPE class names.
ZONE_RULES: dict[str, set[str]] = {
    "general_plant":       {"helmet", "vest"},
    "construction":        {"helmet", "vest", "boots"},
    "work_at_height":      {"helmet", "vest", "boots", "safety_belt", "hook"},
    "restricted_machinery":{"helmet", "vest"},
}

DEFAULT_ZONE = "general_plant"

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://ppe_user:ppe_pass@localhost:5432/ppe_db"
)

# ── Web server ────────────────────────────────────────────────────────────────
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

# ── Camera ────────────────────────────────────────────────────────────────────
DEFAULT_CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
FRAME_WIDTH          = int(os.getenv("FRAME_WIDTH", "1280"))
FRAME_HEIGHT         = int(os.getenv("FRAME_HEIGHT", "720"))
TARGET_FPS           = int(os.getenv("TARGET_FPS", "20"))
