#!/usr/bin/env bash
# ==============================================================================
# EdgeVision / Cerberus AI - Live Demonstration Runner for NVIDIA Jetson Orin
# Demonstrates real-time PPE & Work-at-Height compliance on USB, CSI, RTSP, or Video
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

if [ -d "venv" ]; then
    source venv/bin/activate
fi

SOURCE="0"
ZONE="General Plant Floor"
CONF="0.40"
SHOW_DISPLAY="false"

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --source|-s) SOURCE="$2"; shift ;;
        --zone|-z) ZONE="$2"; shift ;;
        --conf|-c) CONF="$2"; shift ;;
        --display|-d) SHOW_DISPLAY="true" ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --source, -s <src>    Video source (default: 0). Examples:"
            echo "                        0                  (Default USB Webcam /dev/video0)"
            echo "                        csi://0            (Jetson MIPI CSI Camera)"
            echo "                        sample             (Bundled Test Video)"
            echo "                        rtsp://ip:554/live (RTSP IP Camera)"
            echo "                        path/to/video.mp4  (Local Video File)"
            echo "  --zone, -z <zone>     Safety zone (default: 'General Plant Floor')"
            echo "  --conf, -c <float>    Detection confidence threshold (default: 0.40)"
            echo "  --display, -d         Open GUI window on attached HDMI/DisplayPort monitor"
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

if [ "$SOURCE" == "sample" ]; then
    SOURCE="database/evidence/sample_demo.mp4"
    if [ ! -f "$SOURCE" ]; then
        echo "Generating sample demo video..."
        python3 scripts/generate_sample_video.py || true
    fi
fi

echo "============================================================"
echo " 🎥 EdgeVision Jetson Demonstration Mode"
echo " Source: $SOURCE"
echo " Zone  : $ZONE"
echo " Conf  : $CONF"
echo " Display GUI Window: $SHOW_DISPLAY"
echo "============================================================"

python3 -c "
import sys, os, time, cv2
from src.core.vision_pipeline import VisionPipeline
from src.core import config

source = '$SOURCE'
zone = '$ZONE'
conf = float('$CONF')
show_gui = '$SHOW_DISPLAY'.lower() == 'true'

print(f'[INFO] Initializing VisionPipeline for zone: {zone}')
pipeline = VisionPipeline(zone=zone)

# Open camera source
if source.isdigit():
    # Linux V4L2 preferred on Jetson
    cap = cv2.VideoCapture(int(source), cv2.CAP_V4L2)
    if not cap.isOpened():
        cap = cv2.VideoCapture(int(source))
elif source.startswith('csi://'):
    sensor_id = source.replace('csi://', '').strip() or '0'
    gst_str = (
        f'nvarguscamerasrc sensor-id={sensor_id} ! '
        f'video/x-raw(memory:NVMM), width=1280, height=720, framerate=30/1, format=NV12 ! '
        f'nvvidconv ! video/x-raw, format=BGRx ! videoconvert ! video/x-raw, format=BGR ! appsink drop=1'
    )
    print(f'[INFO] Opening Jetson CSI GStreamer Pipeline: {gst_str}')
    cap = cv2.VideoCapture(gst_str, cv2.CAP_GSTREAMER)
else:
    cap = cv2.VideoCapture(source)

if not cap or not cap.isOpened():
    print(f'❌ [ERROR] Could not open video source: {source}')
    print('💡 Tip: If testing without a physical camera, run: ./deploy/jetson/run_demo.sh --source sample')
    sys.exit(1)

print('✅ Video source opened successfully. Processing stream (Press Ctrl+C to stop)...')
frame_idx = 0
t_start = time.time()

try:
    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            if not source.isdigit() and not source.startswith('csi://'):
                # Loop video file for continuous demonstration
                cap.set(cv2.CAP_PROP_POS_MSEC, 0)
                continue
            else:
                print('End of camera stream.')
                break

        t0 = time.perf_counter()
        annotated_frame, worker_states = pipeline.process_frame(frame)
        dt_ms = (time.perf_counter() - t0) * 1000.0

        frame_idx += 1
        elapsed = time.time() - t_start
        fps = frame_idx / elapsed if elapsed > 0 else 0

        # Print live console telemetry every 15 frames
        if frame_idx % 15 == 0:
            workers_count = len(worker_states)
            violations = sum(1 for w in worker_states if not w.get('compliant', True))
            print(f'Frame #{frame_idx:05d} | FPS: {fps:4.1f} | Latency: {dt_ms:4.1f}ms | Workers: {workers_count} | Violations: {violations}')

        if show_gui:
            cv2.imshow('EdgeVision Jetson Live Demonstration', annotated_frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

except KeyboardInterrupt:
    print('\n[INFO] Demonstration stopped by user.')
finally:
    cap.release()
    if show_gui:
        cv2.destroyAllWindows()
    print(f'Processed {frame_idx} frames at average {fps:.1f} FPS.')
"
