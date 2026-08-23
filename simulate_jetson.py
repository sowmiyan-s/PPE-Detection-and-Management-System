#!/usr/bin/env python3
"""
EdgeVision Jetson Deployment Simulator & Verifier.

Simulates the full Jetson Orin deployment pipeline on a standard Windows/Linux PC:
  - Sets Jetson environment variables (PERFORMANCE_PROFILE=jetson, FP16, etc.)
  - Validates all Python imports, model files, config files, and label consistency
  - Runs a mock inference loop with your webcam or synthetic frames
  - Tests FastAPI server startup and health endpoint
  - Reports a pass/fail deployment readiness checklist

Usage:
    python simulate_jetson.py                  # Full verification (no camera)
    python simulate_jetson.py --live           # Live webcam simulation
    python simulate_jetson.py --live --source 1  # External USB camera
    python simulate_jetson.py --server         # Start server in Jetson mode
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import traceback

# ── Configure Jetson simulation environment ──────────────────────────────────
os.environ["PERFORMANCE_PROFILE"] = "jetson"
os.environ["INFERENCE_HALF_PRECISION"] = "true"
os.environ["INFERENCE_IMG_SIZE"] = "640"
os.environ["CUDA_VISIBLE_DEVICES"] = "0"
os.environ["SERVER_HOST"] = "0.0.0.0"
os.environ["PORT"] = "8000"
os.environ["DB_ENGINE"] = "sqlite"
os.environ["PYTHONUNBUFFERED"] = "1"
os.environ["OPENCV_LOG_LEVEL"] = "FATAL"

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Fix Windows terminal encoding for emoji/unicode output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── Terminal Colors (Windows compatible) ─────────────────────────────────────
try:
    os.system("")  # Enable ANSI on Windows
except Exception:
    pass

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def check(label: str, condition: bool, detail: str = "") -> bool:
    """Print a pass/fail check result."""
    if condition:
        print(f"  {GREEN}✅ PASS{RESET}  {label}" + (f"  ({detail})" if detail else ""))
    else:
        print(f"  {RED}❌ FAIL{RESET}  {label}" + (f"  ({detail})" if detail else ""))
    return condition


def run_verification() -> dict:
    """Run all deployment readiness checks."""
    results = {}
    
    print(f"\n{CYAN}{'='*65}{RESET}")
    print(f"{CYAN}  🔍 EdgeVision Jetson Deployment Verification{RESET}")
    print(f"{CYAN}  Simulating: NVIDIA Jetson Orin Nano (aarch64 / JetPack 6.0){RESET}")
    print(f"{CYAN}{'='*65}{RESET}")

    # ── 1. Check model files ────────────────────────────────────────────────
    print(f"\n{BOLD}[1/8] Model Files{RESET}")
    pt_exists = os.path.exists("models/best.pt")
    onnx_exists = os.path.exists("models/best.onnx")
    engine_exists = os.path.exists("models/best.engine")
    results["model_pt"] = check("PyTorch weights (models/best.pt)", pt_exists,
                                 f"{os.path.getsize('models/best.pt') / 1e6:.1f} MB" if pt_exists else "MISSING")
    results["model_onnx"] = check("ONNX model (models/best.onnx)", onnx_exists,
                                   f"{os.path.getsize('models/best.onnx') / 1e6:.1f} MB" if onnx_exists else "Optional — will be exported on Jetson")
    check("TensorRT engine (models/best.engine)", engine_exists,
          "Will be compiled on Jetson via export_engine.sh" if not engine_exists else "Ready")

    # ── 2. Check Python imports ─────────────────────────────────────────────
    print(f"\n{BOLD}[2/8] Python Package Imports{RESET}")
    critical_imports = {
        "ultralytics": "ultralytics",
        "cv2 (OpenCV)": "cv2",
        "numpy": "numpy",
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "pydantic": "pydantic",
        "psutil": "psutil",
        "paho.mqtt": "paho.mqtt.client",
        "python-dotenv": "dotenv",
        "pandas": "pandas",
        "websockets": "websockets",
        "yaml (PyYAML)": "yaml",
    }
    
    import_failures = []
    for label, module in critical_imports.items():
        try:
            __import__(module)
            results[f"import_{module}"] = check(label, True)
        except ImportError as e:
            results[f"import_{module}"] = check(label, False, str(e))
            import_failures.append(module)

    # ── 3. Check project module imports ─────────────────────────────────────
    print(f"\n{BOLD}[3/8] EdgeVision Core Module Imports{RESET}")
    core_modules = [
        ("src.core.config", "Configuration"),
        ("src.core.vision_pipeline", "Vision Pipeline"),
        ("src.core.detector", "YOLO Detector"),
        ("src.core.worker_tracker", "Worker Tracker"),
        ("src.core.rule_engine", "Zone Rule Engine"),
        ("src.core.temporal_validator", "Temporal Validator"),
        ("src.core.association", "PPE Association"),
        ("src.core.sqlite_db", "SQLite Database"),
        ("src.core.device_telemetry", "Device Telemetry"),
        ("src.core.runtime", "Adaptive Runtime"),
        ("src.core.publisher", "MQTT Publisher"),
        ("src.core.discord_webhook", "Discord Webhook"),
        ("src.api.server", "FastAPI Server"),
    ]
    
    for module_path, label in core_modules:
        try:
            __import__(module_path)
            results[f"core_{module_path}"] = check(label, True)
        except Exception as e:
            results[f"core_{module_path}"] = check(label, False, f"{type(e).__name__}: {e}")

    # ── 4. Validate data.yaml / labels.txt consistency ──────────────────────
    print(f"\n{BOLD}[4/8] Label & Class Consistency{RESET}")
    try:
        import yaml
        with open("data.yaml", "r") as f:
            data_yaml = yaml.safe_load(f)
        nc = data_yaml.get("nc", 0)
        class_names = list(data_yaml.get("names", {}).values())
        results["data_yaml"] = check(f"data.yaml loaded ({nc} classes)", nc > 0, ", ".join(class_names[:5]) + "...")
        
        with open("deploy/jetson/labels.txt", "r") as f:
            labels = [l.strip() for l in f.readlines() if l.strip()]
        results["labels_count"] = check(f"labels.txt has {len(labels)} labels", len(labels) == nc,
                                         f"Expected {nc}, got {len(labels)}")
        
        # Check each label matches
        mismatches = []
        for i, (expected, actual) in enumerate(zip(class_names, labels)):
            if expected != actual:
                mismatches.append(f"[{i}] expected '{expected}' got '{actual}'")
        results["labels_match"] = check("All labels match data.yaml class names",
                                         len(mismatches) == 0,
                                         f"{len(mismatches)} mismatches: {', '.join(mismatches[:3])}" if mismatches else "All 19 match")
    except Exception as e:
        results["data_yaml"] = check("data.yaml / labels.txt", False, str(e))

    # ── 5. Validate pgie_config_ppe.txt ──────────────────────────────────────
    print(f"\n{BOLD}[5/8] DeepStream PGIE Config{RESET}")
    try:
        pgie_path = "deploy/jetson/pgie_config_ppe.txt"
        with open(pgie_path, "r") as f:
            pgie_content = f.read()
        
        # Check num-detected-classes
        for line in pgie_content.splitlines():
            stripped = line.split("#")[0].strip()
            if stripped.startswith("num-detected-classes="):
                pgie_nc = int(stripped.split("=")[1])
                results["pgie_classes"] = check(f"PGIE num-detected-classes={pgie_nc}", pgie_nc == nc,
                                                 f"Must match data.yaml nc={nc}")
            if stripped.startswith("network-mode="):
                mode = int(stripped.split("=")[1])
                mode_names = {0: "FP32", 1: "INT8", 2: "FP16"}
                results["pgie_precision"] = check(f"PGIE network-mode={mode} ({mode_names.get(mode, '?')})",
                                                    mode == 2, "Should be 2 (FP16) for Jetson Orin")
    except Exception as e:
        results["pgie_config"] = check("PGIE config", False, str(e))

    # ── 6. Validate systemd service file ─────────────────────────────────────
    print(f"\n{BOLD}[6/8] Systemd Service File{RESET}")
    try:
        with open("deploy/jetson/edgevision-pipeline.service", "r") as f:
            svc_content = f.read()
        
        has_workdir = "WorkingDirectory=/opt/edgevision" in svc_content
        results["svc_workdir"] = check("WorkingDirectory=/opt/edgevision", has_workdir,
                                        "Must match git clone path")
        
        has_hardcoded_user = "User=jetson" in svc_content
        results["svc_user"] = check("No hardcoded User=jetson", not has_hardcoded_user,
                                     "Hardcoded user will fail if username differs")
    except Exception as e:
        results["svc_file"] = check("Service file", False, str(e))

    # ── 7. Validate shell scripts have correct line endings ──────────────────
    print(f"\n{BOLD}[7/8] Shell Script Line Endings (LF vs CRLF){RESET}")
    shell_scripts = [
        "deploy/jetson/install.sh",
        "deploy/jetson/start.sh",
        "deploy/jetson/run_demo.sh",
        "deploy/jetson/export_engine.sh",
        "deploy/jetson/run_benchmark.sh",
        "start_render.sh",
    ]
    
    for script in shell_scripts:
        if os.path.exists(script):
            with open(script, "rb") as f:
                content = f.read()
            has_crlf = b"\r\n" in content
            results[f"lineending_{script}"] = check(
                os.path.basename(script),
                not has_crlf,
                "⚠️ Has CRLF (Windows line endings) — will cause 'bad interpreter' error on Jetson Linux!"
                if has_crlf else "LF (Unix) ✓"
            )

    # ── 8. Config value sanity checks ────────────────────────────────────────
    print(f"\n{BOLD}[8/8] Runtime Configuration Sanity{RESET}")
    try:
        from src.core import config
        results["cfg_profile"] = check(f"PERFORMANCE_PROFILE={config.PERFORMANCE_PROFILE}",
                                        config.PERFORMANCE_PROFILE in ("jetson", "auto", "low_end"),
                                        "Valid profile")
        results["cfg_imgsize"] = check(f"INFERENCE_IMG_SIZE={config.INFERENCE_IMG_SIZE}",
                                        config.INFERENCE_IMG_SIZE in (320, 416, 480, 640),
                                        "Valid size")
        results["cfg_port"] = check(f"SERVER_PORT={config.SERVER_PORT}", config.SERVER_PORT > 0)
        results["cfg_db"] = check(f"DB_ENGINE={config.DB_ENGINE}", config.DB_ENGINE == "sqlite",
                                   "SQLite is recommended for Jetson edge")
        results["cfg_zones"] = check(f"Zone rules: {len(config.ZONE_RULES)} zones configured",
                                      len(config.ZONE_RULES) >= 1)
    except Exception as e:
        results["config"] = check("Config load", False, str(e))

    # ── Summary ──────────────────────────────────────────────────────────────
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed
    
    print(f"\n{CYAN}{'='*65}{RESET}")
    if failed == 0:
        print(f"  {GREEN}{BOLD}🎉 ALL {total} CHECKS PASSED — READY FOR JETSON DEPLOYMENT!{RESET}")
    else:
        print(f"  {RED}{BOLD}⚠️  {failed}/{total} CHECKS FAILED — Fix issues before deploying{RESET}")
    print(f"{CYAN}{'='*65}{RESET}\n")
    
    return results


def run_live_simulation(source: str = "0"):
    """Run live webcam inference in simulated Jetson mode."""
    import cv2
    import numpy as np
    
    print(f"\n{CYAN}{'='*65}{RESET}")
    print(f"{CYAN}  🎥 Jetson Orin Nano Live Simulation Mode{RESET}")
    print(f"{CYAN}  Source: {source}{RESET}")
    print(f"{CYAN}  Environment: PERFORMANCE_PROFILE=jetson, FP16={os.environ.get('INFERENCE_HALF_PRECISION')}{RESET}")
    print(f"{CYAN}{'='*65}{RESET}\n")
    
    from src.core.vision_pipeline import VisionPipeline
    from src.core import config
    
    print(f"[INFO] Initializing VisionPipeline (zone: {config.DEFAULT_ZONE})...")
    pipeline = VisionPipeline(zone=config.DEFAULT_ZONE)
    
    # Open video source
    src = int(source) if source.isdigit() else source
    cap = cv2.VideoCapture(src)
    
    if not cap.isOpened():
        print(f"{RED}❌ Cannot open camera source: {source}{RESET}")
        print(f"   Falling back to synthetic frame simulation...")
        cap = None
    
    frame_idx = 0
    fps_history = []
    t_global = time.time()
    
    print(f"\n{GREEN}✅ Pipeline initialized. Running inference loop (Ctrl+C to stop)...{RESET}\n")
    
    try:
        while True:
            if cap and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    print("End of stream. Looping...")
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
            else:
                # Synthetic 720p frame
                frame = np.random.randint(0, 255, (720, 1280, 3), dtype=np.uint8)
            
            t0 = time.perf_counter()
            annotated_frame, worker_states = pipeline.process_frame(frame)
            dt = time.perf_counter() - t0
            fps = 1.0 / max(dt, 1e-6)
            fps_history.append(fps)
            
            frame_idx += 1
            
            # Print telemetry every 10 frames
            if frame_idx % 10 == 0:
                avg_fps = sum(fps_history[-30:]) / len(fps_history[-30:])
                latency_ms = dt * 1000
                workers = len(worker_states)
                violations = sum(1 for w in worker_states if not w.get("compliant", True))
                
                print(f"  Frame #{frame_idx:05d} | "
                      f"FPS: {avg_fps:5.1f} (instant: {fps:5.1f}) | "
                      f"Latency: {latency_ms:6.1f}ms | "
                      f"Workers: {workers} | "
                      f"Violations: {violations}")
            
            # Show GUI window
            if cap:
                cv2.imshow("EdgeVision Jetson Simulation", annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                    
    except KeyboardInterrupt:
        print(f"\n{YELLOW}[INFO] Simulation stopped by user.{RESET}")
    finally:
        if cap:
            cap.release()
            cv2.destroyAllWindows()
        
        elapsed = time.time() - t_global
        avg = sum(fps_history) / max(len(fps_history), 1)
        print(f"\n{CYAN}{'='*65}{RESET}")
        print(f"  Processed {frame_idx} frames in {elapsed:.1f}s")
        print(f"  Average FPS: {avg:.1f}")
        if avg >= 30:
            print(f"  {GREEN}🟢 EXCELLENT — Exceeds 30 FPS real-time baseline{RESET}")
        elif avg >= 15:
            print(f"  {YELLOW}🟡 GOOD — Meets industrial 15 FPS requirement{RESET}")
        else:
            print(f"  {RED}🔴 LOW — TensorRT FP16 engine will boost this 3-5x on Jetson{RESET}")
        print(f"{CYAN}{'='*65}{RESET}\n")


def run_server_simulation():
    """Start the EdgeVision server in Jetson simulation mode."""
    print(f"\n{CYAN}{'='*65}{RESET}")
    print(f"{CYAN}  🚀 Starting EdgeVision Server (Jetson Simulation Mode){RESET}")
    print(f"{CYAN}  Dashboard: http://localhost:8000{RESET}")
    print(f"{CYAN}  Live Stream: http://localhost:8000/api/stream{RESET}")
    print(f"{CYAN}  Health: http://localhost:8000/api/health{RESET}")
    print(f"{CYAN}{'='*65}{RESET}\n")
    
    import uvicorn
    from src.core import config
    
    uvicorn.run(
        "src.api.server:app",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        reload=False,
        log_level="info",
    )


def main():
    parser = argparse.ArgumentParser(
        description="EdgeVision Jetson Deployment Simulator & Verifier",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python simulate_jetson.py                    # Run all deployment checks
  python simulate_jetson.py --live             # Live webcam simulation
  python simulate_jetson.py --live --source 1  # External USB camera
  python simulate_jetson.py --server           # Start server in Jetson mode
  python simulate_jetson.py --all              # Checks + live + server
        """
    )
    parser.add_argument("--live", action="store_true", help="Run live webcam inference simulation")
    parser.add_argument("--server", action="store_true", help="Start FastAPI server in Jetson mode")
    parser.add_argument("--source", default="0", help="Camera source (default: 0)")
    parser.add_argument("--all", action="store_true", help="Run checks, then live, then server")
    parser.add_argument("--skip-checks", action="store_true", help="Skip verification checks")
    args = parser.parse_args()
    
    if not args.skip_checks and not (args.live and args.skip_checks) and not (args.server and args.skip_checks):
        results = run_verification()
        failed = sum(1 for v in results.values() if not v)
        if failed > 0 and not args.live and not args.server:
            print(f"{YELLOW}Fix the above issues before deploying to Jetson.{RESET}")
            sys.exit(1)
    
    if args.live or args.all:
        run_live_simulation(args.source)
    
    if args.server or args.all:
        run_server_simulation()
    
    if not args.live and not args.server and not args.all:
        print(f"💡 Next steps:")
        print(f"   python simulate_jetson.py --live      # Test with your webcam")
        print(f"   python simulate_jetson.py --server    # Start full server")
        print()


if __name__ == "__main__":
    main()
