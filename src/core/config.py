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
    "models/best.pt" if os.path.exists("models/best.pt") else "best.pt"
)
FALLBACK_MODEL_PATH = os.getenv("FALLBACK_MODEL_PATH", "models/best.pt")
DETECTION_CONF      = float(os.getenv("DETECTION_CONF", "0.45"))
TRACKER_CONFIG      = "bytetrack.yaml"

PERFORMANCE_PROFILE = os.getenv("PERFORMANCE_PROFILE", "auto").lower()

def _check_gpu() -> bool:
    try:
        import torch
        return bool(torch.cuda.is_available())
    except Exception:
        return False

IS_GPU_AVAILABLE = _check_gpu()


# Inference Optimization (Jetson / TensorRT / FP16 / Adaptive Hardware Profiles)
if PERFORMANCE_PROFILE == "low_end" or (PERFORMANCE_PROFILE == "auto" and not IS_GPU_AVAILABLE):
    # Low-end system profile (8GB RAM / CPU-only laptop) - maximize responsiveness & zero camera lag
    INFERENCE_IMG_SIZE       = int(os.getenv("INFERENCE_IMG_SIZE", "480"))
    INFERENCE_HALF_PRECISION = os.getenv("INFERENCE_HALF_PRECISION", "false").lower() == "true"
    FRAME_SKIP_INTERVAL      = int(os.getenv("FRAME_SKIP_INTERVAL", "1"))  # Run inference on alternating frames
    STREAM_MAX_WIDTH         = int(os.getenv("STREAM_MAX_WIDTH", "854"))     # 480p preview stream
    JPEG_QUALITY             = int(os.getenv("JPEG_QUALITY", "50"))
else:
    # High-end system profile (Discrete GPU / Jetson Edge / Multi-Core)
    INFERENCE_IMG_SIZE       = int(os.getenv("INFERENCE_IMG_SIZE", "640"))
    INFERENCE_HALF_PRECISION = os.getenv("INFERENCE_HALF_PRECISION", "true").lower() == "true"
    FRAME_SKIP_INTERVAL      = int(os.getenv("FRAME_SKIP_INTERVAL", "0"))  # Run inference every frame
    STREAM_MAX_WIDTH         = int(os.getenv("STREAM_MAX_WIDTH", "640"))
    JPEG_QUALITY             = int(os.getenv("JPEG_QUALITY", "65"))

# ── PPE classes (must match model / data.yaml order) ─────────────────────────
PPE_CLASSES = [
    "Boots",                 # 0
    "Ear-Protection",        # 1
    "Glass",                 # 2
    "Glove",                 # 3
    "Hard_hat",              # 4
    "Mask",                  # 5
    "No-Boots",              # 6
    "No-Ear-Protection",     # 7
    "No-Glass",              # 8
    "No-Glove",              # 9
    "No-Helmet",             # 10
    "No-Mask",               # 11
    "No-Vest",               # 12
    "Worker",                # 13
    "Vest",                  # 14
    "Circular_Saw",          # 15
    "Fire_Extinguisher",     # 16
    "Fire_prevention_Net",   # 17
    "Welding_Equipment",     # 18
    # Canonical normalized keys
    "person",
    "helmet",
    "vest",
    "boots",
    "gloves",
    "glasses",
    "mask",
    "earmuffs",
]

# ── Stage-3 association ───────────────────────────────────────────────────────
PPE_CONTAINMENT_THRESHOLD = float(os.getenv("PPE_CONTAINMENT_THRESHOLD", "0.40"))

# ── Stage-5 temporal validation ───────────────────────────────────────────────
TEMPORAL_WINDOW        = int(os.getenv("TEMPORAL_WINDOW", "10"))        # frames
TEMPORAL_MIN_HITS      = int(os.getenv("TEMPORAL_MIN_HITS", "8"))       # out of WINDOW (matches spec requirement: 8 of 10)
TEMPORAL_MIN_CONF      = float(os.getenv("TEMPORAL_MIN_CONF", "0.20")) # confidence
TEMPORAL_MIN_ZONE_SECS = float(os.getenv("TEMPORAL_MIN_ZONE_SECS", "5.0")) # default dwell time: 5.0 seconds

# ── Persistent worker tracker (majority voting across frames) ─────────────────
WORKER_TRACKER_WINDOW    = int(os.getenv("WORKER_TRACKER_WINDOW", "8"))    # sliding window size
WORKER_TRACKER_MIN_VOTES = int(os.getenv("WORKER_TRACKER_MIN_VOTES", "3"))  # min detections to confirm PPE
WORKER_TRACKER_STALE_FRAMES = int(os.getenv("WORKER_TRACKER_STALE_FRAMES", "60"))  # cleanup after N absent frames

# ── Violation deduplication ───────────────────────────────────────────────────
VIOLATION_COOLDOWN_SECS = float(os.getenv("VIOLATION_COOLDOWN_SECS", "5.0"))   # per-worker DB write cooldown

# ── PPE Aliases & Normalization ───────────────────────────────────────────────
PPE_ALIASES: dict[str, str] = {
    # Helmet / Hard hat
    "helmet":            "helmet",
    "Helmet":            "helmet",
    "Hard_hat":          "helmet",
    "no_helmet":         "helmet",
    "no-helmet":         "helmet",
    "No-Helmet":         "helmet",
    
    # Vest
    "vest":              "vest",
    "Vest":              "vest",
    "no_vest":           "vest",
    "no-vest":           "vest",
    "No-Vest":           "vest",
    
    # Boots
    "boots":             "boots",
    "Boots":             "boots",
    "no_boots":          "boots",
    "no-boots":          "boots",
    "No-Boots":          "boots",
    
    # Glasses / Goggles / Eye Protection
    "glasses":           "glasses",
    "glass":             "glasses",
    "Glass":             "glasses",
    "goggles":           "glasses",
    "no_glass":          "glasses",
    "no-goggles":        "glasses",
    "No-Glass":          "glasses",
    
    # Gloves
    "glove":             "gloves",
    "gloves":            "gloves",
    "Glove":             "gloves",
    "no_gloves":         "gloves",
    "no-glove":          "gloves",
    "No-Glove":          "gloves",
    
    # Mask
    "mask":              "mask",
    "Mask":              "mask",
    "no_mask":           "mask",
    "no-mask":           "mask",
    "No-Mask":           "mask",
    
    # Ear Protection / Earmuffs
    "earmuffs":          "earmuffs",
    "Ear-protection":    "earmuffs",
    "Ear-Protection":    "earmuffs",
    "ear_protection":    "earmuffs",
    "no_earmuffs":       "earmuffs",
    "no-ear-protection": "earmuffs",
    "No-Ear-Protection": "earmuffs",

    # Worker / Person
    "Worker":            "person",
    "worker":            "person",
    "person":            "person",
    "Person":            "person",
}

# ── Zone rule engine (Stage-4) ────────────────────────────────────────────────
# Each zone maps to a set of required PPE class names.
ZONE_RULES: dict[str, set[str]] = {
    "General Plant Floor":       {"helmet", "vest"},
    "Construction Area":        {"helmet", "vest", "boots"},
    "Work at Height Platform":      {"helmet", "vest", "boots"},
    "Restricted Machinery Zone": {"helmet", "vest", "glasses"},
    "Hazardous Chemical Area":  {"helmet", "vest", "boots", "glasses", "mask", "gloves"},
}

DEFAULT_ZONE = "General Plant Floor"

# ── Database ──────────────────────────────────────────────────────────────────
DB_ENGINE = os.getenv("DB_ENGINE", "sqlite").lower() # "sqlite" or "postgresql"
DUAL_DB_SYNC = False # Dual DB sync deprecated after MongoDB removal

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://ppe_user:ppe_pass@localhost:5432/ppe_db"
)

def set_db_engine(engine: str) -> str:
    global DB_ENGINE
    engine_clean = engine.strip().lower()
    if engine_clean in ("postgresql", "postgres", "rdbms"):
        DB_ENGINE = "postgresql"
    else:
        DB_ENGINE = "sqlite"
    os.environ["DB_ENGINE"] = DB_ENGINE
    return DB_ENGINE

def set_dual_db_sync(enabled: bool) -> bool:
    global DUAL_DB_SYNC
    DUAL_DB_SYNC = False
    return DUAL_DB_SYNC

# ── Web server ────────────────────────────────────────────────────────────────
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("PORT", os.getenv("SERVER_PORT", "8000")))

# ── Camera ────────────────────────────────────────────────────────────────────
DEFAULT_CAMERA_SOURCE = os.getenv("CAMERA_SOURCE", "0")
DEFAULT_CAMERA_INDEX  = DEFAULT_CAMERA_SOURCE
FRAME_WIDTH          = int(os.getenv("FRAME_WIDTH", "640"))
FRAME_HEIGHT         = int(os.getenv("FRAME_HEIGHT", "480"))
TARGET_FPS           = int(os.getenv("TARGET_FPS", "60"))
