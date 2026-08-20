"""
EdgeVision Server Entry Point
"""

import os
os.environ["OPENCV_LOG_LEVEL"] = "FATAL"
os.environ["OPENCV_FFMPEG_LOGLEVEL"] = "-8"
os.environ["AV_LOG_LEVEL"] = "quiet"
import sys
import uvicorn

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.api.server import app
from src.core import config

if __name__ == "__main__":
    port = int(os.getenv("PORT", config.SERVER_PORT))
    print(f"Starting EdgeVision Server on {config.SERVER_HOST}:{port}...")
    uvicorn.run("src.api.server:app", host=config.SERVER_HOST, port=port, reload=True)
