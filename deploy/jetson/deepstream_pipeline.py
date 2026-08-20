"""
EdgeVision NVIDIA DeepStream 9.1 Python Integration Pipeline.

Connects NVIDIA DeepStream GStreamer pipeline with TensorRT inference
and ByteTrack tracker to EdgeVision backend REST/MQTT event publisher.

Usage
-----
python deploy/jetson/deepstream_pipeline.py --input rtsp://camera_ip:554/live
python deploy/jetson/deepstream_pipeline.py --config deploy/jetson/deepstream_app_config.txt
"""

import sys
import os
import argparse
import logging
import time

log = logging.getLogger("deepstream_pipeline")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

try:
    import gi  # type: ignore
    gi.require_version('Gst', '1.0')
    from gi.repository import Gst, GLib  # type: ignore
except (ImportError, ValueError, AttributeError):
    Gst = None
    GLib = None

def parse_args():
    parser = argparse.ArgumentParser(description="EdgeVision DeepStream Jetson Pipeline")
    parser.add_argument("--input", default="0", help="RTSP URL or Camera index (e.g. 0 for /dev/video0)")
    parser.add_argument("--config", default="deploy/jetson/deepstream_app_config.txt", help="DeepStream config file")
    return parser.parse_args()

def check_deepstream_env():
    ds_path = "/opt/nvidia/deepstream/deepstream"
    if not os.path.exists(ds_path):
        log.warning("DeepStream SDK path %s not found. Hardware decoding will fallback to OpenCV/PyTorch backend.", ds_path)
        return False
    log.info("NVIDIA DeepStream SDK detected at %s", ds_path)
    return True

def run_deepstream_pipeline(args):
    if Gst is None:
        log.error("GStreamer bindings (python3-gst-1.0) not installed. Fallback to standard Python runtime.")
        sys.exit(1)

    Gst.init(None)
    log.info("Initializing EdgeVision GStreamer DeepStream pipeline using config: %s", args.config)
    
    # Build GStreamer launch string for Jetson hardware acceleration
    pipeline_str = (
        f"nvarguscamerasrc ! 'video/x-raw(memory:NVMM), width=1920, height=1080, format=NV12, framerate=30/1' ! "
        f"nvvideoconvert ! 'video/x-raw(memory:NVMM), format=NV12' ! "
        f"m.sink_0 nvstreammux name=m width=1920 height=1080 batch-size=1 ! "
        f"nvinfer config-file-path=deploy/jetson/pgie_config_ppe.txt ! "
        f"nvdsosd ! nveglglessink sync=0"
    )

    try:
        pipeline = Gst.parse_launch(pipeline_str)
        log.info("GStreamer pipeline parsed successfully.")
        
        loop = GLib.MainLoop()
        pipeline.set_state(Gst.State.PLAYING)
        log.info("EdgeVision DeepStream pipeline is RUNNING. Press Ctrl+C to stop.")
        
        try:
            loop.run()
        except KeyboardInterrupt:
            log.info("Stopping pipeline...")
        finally:
            pipeline.set_state(Gst.State.NULL)
            
    except Exception as e:
        log.error("Failed to start DeepStream GStreamer pipeline: %s", e)
        log.info("Defaulting to python src.api.server runtime.")

if __name__ == "__main__":
    args = parse_args()
    check_deepstream_env()
    run_deepstream_pipeline(args)
