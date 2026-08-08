"""
Central configuration for the EdgeVision PPE Compliance Platform.
All tuneable values live here; environment variables override where relevant.
"""

import os
from dotenv import load_dotenv

load_dotenv()

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
FALLBACK_MODEL_PATH = "models/yolo11n.pt"
DETECTION_CONF      = float(os.getenv("DETECTION_CONF", "0.20"))
TRACKER_CONFIG      = "bytetrack.yaml"

# Inference Optimization (Jetson / TensorRT / FP16)
INFERENCE_IMG_SIZE       = int(os.getenv("INFERENCE_IMG_SIZE", "640"))
INFERENCE_HALF_PRECISION = os.getenv("INFERENCE_HALF_PRECISION", "true").lower() == "true"

# ── PPE classes (must match data.yaml order) ───────────────────────────────
PPE_CLASSES = [
    "helmet",
    "no-helmet",
    "vest",
    "no-vest",
    "person",
    "gloves",
    "no-gloves",
    "boots",
    "no-boots",
    "goggles",
    "no-goggles",
    "ear-mufs",
    "face-guard",
    "safety-suit",
    "tool",
]

# ── Stage-3 association ───────────────────────────────────────────────────────
PPE_CONTAINMENT_THRESHOLD = float(os.getenv("PPE_CONTAINMENT_THRESHOLD", "0.40"))

# ── Stage-5 temporal validation ───────────────────────────────────────────────
TEMPORAL_WINDOW        = int(os.getenv("TEMPORAL_WINDOW", "8"))        # frames
TEMPORAL_MIN_HITS      = int(os.getenv("TEMPORAL_MIN_HITS", "5"))      # out of WINDOW
TEMPORAL_MIN_CONF      = float(os.getenv("TEMPORAL_MIN_CONF", "0.30")) # confidence
TEMPORAL_MIN_ZONE_SECS = float(os.getenv("TEMPORAL_MIN_ZONE_SECS", "2.0"))  # seconds

# ── Persistent worker tracker (majority voting across frames) ─────────────────
WORKER_TRACKER_WINDOW    = int(os.getenv("WORKER_TRACKER_WINDOW", "10"))   # sliding window size
WORKER_TRACKER_MIN_VOTES = int(os.getenv("WORKER_TRACKER_MIN_VOTES", "5")) # min detections to confirm PPE
WORKER_TRACKER_STALE_FRAMES = int(os.getenv("WORKER_TRACKER_STALE_FRAMES", "60"))  # cleanup after N absent frames

# ── Violation deduplication ───────────────────────────────────────────────────
VIOLATION_COOLDOWN_SECS = float(os.getenv("VIOLATION_COOLDOWN_SECS", "30.0"))  # per-worker DB write cooldown

# ── Zone rule engine (Stage-4) ────────────────────────────────────────────────
# Each zone maps to a set of required PPE class names.
ZONE_RULES: dict[str, set[str]] = {
    "general_plant":       {"helmet", "vest"},
    "restricted_machinery":{"helmet", "vest", "goggles", "ear-mufs", "face-guard"},
    "hazardous_material":  {"helmet", "safety-suit", "boots", "gloves", "goggles"},
}

DEFAULT_ZONE = "general_plant"

# ── Database ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://ppe_user:ppe_pass@localhost:5432/ppe_db"
)
MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb://localhost:27017"
)
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "edgevision")

# ── Web server ────────────────────────────────────────────────────────────────
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))

# ── Camera ────────────────────────────────────────────────────────────────────
DEFAULT_CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
FRAME_WIDTH          = int(os.getenv("FRAME_WIDTH", "1280"))
FRAME_HEIGHT         = int(os.getenv("FRAME_HEIGHT", "720"))
TARGET_FPS           = int(os.getenv("TARGET_FPS", "20"))
