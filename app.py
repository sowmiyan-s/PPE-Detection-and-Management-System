"""
EdgeVision PPE Compliance Dashboard – Streamlit multi-page application.

Pages
-----
  Live Monitoring      – real-time camera feed with detection overlays
  Active Violations    – current safety violations across all workers
  Event History        – searchable log of past incidents
  Worker Compliance    – per-worker compliance statistics
  Zone Configuration   – configure required PPE per zone
  Camera Management    – add and manage camera sources
  Reports              – daily / weekly / monthly safety summaries
  Model Monitoring     – model version, FPS, and accuracy statistics
"""

from __future__ import annotations

import json
import os
import queue
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import cv2
import paho.mqtt.client as mqtt
import streamlit as st

import config
from detector import PPEDetector
from rule_engine import RuleEngine

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="EdgeVision PPE Dashboard",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────

st.markdown("""
<style>
.metric-card {
    background: #1e2330; border: 1px solid #2d3448; border-radius: 8px;
    padding: 16px; margin-bottom: 12px;
}
.violation-card {
    background: #2d1b1b; border-left: 4px solid #e53935; border-radius: 6px;
    padding: 12px; margin-bottom: 10px;
}
.compliant-card {
    background: #1b2d1b; border-left: 4px solid #43a047; border-radius: 6px;
    padding: 12px; margin-bottom: 10px;
}
.worker-id    { font-weight: 700; font-size: 1.05rem; }
.missing-ppe  { color: #ef5350; font-weight: 600; }
.present-ppe  { color: #66bb6a; }
.badge        { display: inline-block; padding: 2px 10px; border-radius: 12px;
                font-size: 0.78rem; margin: 2px; }
.badge-red    { background: #b71c1c; color: #fff; }
.badge-green  { background: #1b5e20; color: #fff; }
.badge-blue   { background: #0d47a1; color: #fff; }
</style>
""", unsafe_allow_html=True)

# ── Session state initialisation ───────────────────────────────────────────────

def _init_state() -> None:
    defaults: dict = {
        "logs":             [],          # MQTT violation events
        "mqtt_queue":       queue.Queue(),
        "live_running":     False,
        "camera_source":    0,
        "active_zone":      config.DEFAULT_ZONE,
        "cameras":          [{"id": "cam_0", "name": "Camera 0", "source": 0}],
        "event_history":    deque(maxlen=500),
        "worker_stats":     defaultdict(lambda: {"violations": 0, "frames": 0, "last_seen": None}),
        "fps_history":      deque(maxlen=60),
        "model_version":    "yolov8n-base",
        "model_map50":      None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ── MQTT client ────────────────────────────────────────────────────────────────

def _on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        st.session_state.mqtt_queue.put(payload)
    except Exception:
        pass


@st.cache_resource
def _get_mqtt_client():
    client = mqtt.Client(protocol=mqtt.MQTTv311)
    if config.MQTT_USERNAME:
        client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
    if config.MQTT_USE_TLS:
        client.tls_set()
    client.on_message = _on_message
    try:
        client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
        client.subscribe(config.MQTT_TOPIC)
        client.loop_start()
    except Exception as exc:
        st.sidebar.warning(f"MQTT unavailable: {exc}")
    return client


def _drain_mqtt_queue() -> list[dict]:
    """Pull all pending MQTT messages from the thread-safe queue."""
    events: list[dict] = []
    q = st.session_state.mqtt_queue
    while not q.empty():
        try:
            events.append(q.get_nowait())
        except queue.Empty:
            break
    return events


# ── Detector cache ─────────────────────────────────────────────────────────────

@st.cache_resource
<<<<<<< HEAD
def get_detector():
    trained_model = "custom_model-3/weights/best.pt"
    if os.path.exists(trained_model):
        st.sidebar.success(f"Loaded custom model: {trained_model}")
        return PPEDetector(model_path=trained_model, mqtt_broker=MQTT_BROKER, mqtt_port=MQTT_PORT)
=======
def _get_detector(zone: str = config.DEFAULT_ZONE) -> PPEDetector:
    model_path = config.DEFAULT_MODEL_PATH
    if not os.path.exists(model_path):
        model_path = config.FALLBACK_MODEL_PATH
    return PPEDetector(model_path=model_path, zone=zone)


# ── Rule engine (for Zone Config page) ────────────────────────────────────────
@st.cache_resource
def _get_rule_engine() -> RuleEngine:
    return RuleEngine()


# ── Sidebar navigation ─────────────────────────────────────────────────────────

_mqtt_client = _get_mqtt_client()

st.sidebar.title("🏭 EdgeVision")
st.sidebar.markdown("**PPE Compliance Platform**")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigation",
    [
        "📷 Live Monitoring",
        "🚨 Active Violations",
        "📋 Event History",
        "👷 Worker Compliance",
        "🗺️ Zone Configuration",
        "📹 Camera Management",
        "📊 Reports",
        "🤖 Model Monitoring",
    ],
)

st.sidebar.divider()
broker_status = "🟢 Connected" if _mqtt_client else "🔴 Disconnected"
st.sidebar.caption(f"MQTT: {broker_status}")
st.sidebar.caption(f"Broker: `{config.MQTT_BROKER}:{config.MQTT_PORT}`")

# ── Shared: drain MQTT and update state ───────────────────────────────────────

new_events = _drain_mqtt_queue()
for ev in new_events:
    st.session_state.logs.append(ev)
    st.session_state.event_history.appendleft(ev)
    wid = ev.get("worker_id", "unknown")
    st.session_state.worker_stats[wid]["violations"] += 1
    st.session_state.worker_stats[wid]["last_seen"]   = ev.get("timestamp")

# cap logs at 200
if len(st.session_state.logs) > 200:
    st.session_state.logs = st.session_state.logs[-200:]


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Live Monitoring
# ══════════════════════════════════════════════════════════════════════════════

if page == "📷 Live Monitoring":
    st.title("📷 Live Monitoring")
    col_ctrl, col_info = st.columns([2, 1])

    with col_ctrl:
        source_opt = st.selectbox(
            "Camera source",
            options=["Webcam (0)", "Webcam (1)", "RTSP stream", "Video file"],
        )
        if source_opt == "Webcam (0)":
            source = 0
        elif source_opt == "Webcam (1)":
            source = 1
        elif source_opt == "RTSP stream":
            source = st.text_input("RTSP URL", placeholder="rtsp://192.168.1.x/stream")
        else:
            source = st.text_input("Video file path", placeholder="/data/footage.mp4")

    with col_info:
        active_zone = st.selectbox(
            "Active zone",
            options=list(config.ZONE_RULES.keys()),
            format_func=lambda z: z.replace("_", " ").title(),
            index=list(config.ZONE_RULES.keys()).index(config.DEFAULT_ZONE),
        )
        st.session_state.active_zone = active_zone

    run = st.checkbox("▶ Start detection", value=st.session_state.live_running)
    st.session_state.live_running = run

    frame_placeholder  = st.empty()
    status_placeholder = st.empty()

    if run:
        detector = _get_detector(active_zone)
        cap = cv2.VideoCapture(source if isinstance(source, int) else str(source))

        if not cap.isOpened():
            st.error(f"Cannot open camera source: {source}")
        else:
            st.info("Detection running. Uncheck to stop.")
            while st.session_state.live_running:
                ok, frame = cap.read()
                if not ok:
                    st.warning("Frame read failed. Check camera source.")
                    break

                t0 = time.perf_counter()
                annotated, workers = detector.process_frame(frame, zone=active_zone)
                fps = 1.0 / max(time.perf_counter() - t0, 1e-6)
                st.session_state.fps_history.append(fps)

                rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
                frame_placeholder.image(rgb, channels="RGB", use_container_width=True)

                # Update MQTT events
                new_ev = _drain_mqtt_queue()
                for ev in new_ev:
                    st.session_state.logs.append(ev)
                    st.session_state.event_history.appendleft(ev)

                # Worker status cards
                with status_placeholder.container():
                    cols = st.columns(min(len(workers), 4) or 1)
                    for i, w in enumerate(workers):
                        with cols[i % len(cols)]:
                            card_cls = "compliant-card" if w["compliant"] else "violation-card"
                            missing  = ", ".join(w.get("missing_ppe", [])) or "—"
                            present  = ", ".join(w.get("detected_ppe", [])) or "—"
                            st.markdown(f"""
<div class="{card_cls}">
  <div class="worker-id">{w['worker_id']}</div>
  <div>Zone: <strong>{w['zone'].replace('_',' ').title()}</strong></div>
  <div class="present-ppe">✓ {present}</div>
  {"" if w['compliant'] else f'<div class="missing-ppe">✗ Missing: {missing}</div>'}
  <small>conf {w.get("confidence", 0):.0%} | {fps:.1f} fps</small>
</div>""", unsafe_allow_html=True)

            cap.release()
>>>>>>> 23bb9ced683c99cd7b7cc1433e6c86b5f075baf1
    else:
        frame_placeholder.info("Detection paused. Check 'Start detection' to begin.")


<<<<<<< HEAD
with col1:
    st.subheader("Live Surveillance Feed")
    
    # Input options
    import glob
    video_source = st.selectbox("Select Video Source", ["0 (Webcam)", "Dataset Image (Test)", "rtsp://simulated.stream", "simulated.mp4"])
    
    if video_source == "Dataset Image (Test)":
        test_images = glob.glob("datasets/ppe_dataset/images/train/*.jpg")[:10]
        selected_image = st.selectbox("Select Image from Dataset", test_images)
        run = st.button("▶️ Process Image")
    else:
        run = st.checkbox("▶️ Start Surveillance", value=False)
    
    # Placeholders for video and metrics
    frame_placeholder = st.empty()
=======
# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Active Violations
# ══════════════════════════════════════════════════════════════════════════════
>>>>>>> 23bb9ced683c99cd7b7cc1433e6c86b5f075baf1

elif page == "🚨 Active Violations":
    st.title("🚨 Active Violations")

    logs = st.session_state.logs
    if not logs:
        st.success("✅ No violations recorded yet.")
    else:
        recent = sorted(logs, key=lambda e: e.get("timestamp", ""), reverse=True)[:50]
        st.markdown(f"**{len(recent)} most recent violations**")

        for ev in recent:
            ts      = ev.get("timestamp", "—")
            wid     = ev.get("worker_id", "—")
            zone    = ev.get("zone", "—").replace("_", " ").title()
            missing = ", ".join(ev.get("missing_ppe", []))
            present = ", ".join(ev.get("detected_ppe", []))
            conf    = ev.get("confidence", 0)

<<<<<<< HEAD
if run:
    detector = get_detector()
    
    if video_source == "Dataset Image (Test)":
        frame = cv2.imread(selected_image)
        if frame is not None:
            processed_frame = detector.process_frame(frame)
            frame_rgb = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
            frame_placeholder.image(frame_rgb, channels="RGB", use_container_width=True)
            
            # Process MQTT Queue for New Alerts
            while not st.session_state.mqtt_queue.empty():
                alert = st.session_state.mqtt_queue.get()
                st.session_state.logs.insert(0, alert)
                if len(st.session_state.logs) > 50:
                    st.session_state.logs.pop()
                    
            with log_placeholder.container():
                if not st.session_state.logs:
                    st.markdown('<p class="compliant-text">✅ No violations detected yet.</p>', unsafe_allow_html=True)
                for log in st.session_state.logs:
                    missing = ", ".join(log['missing_equipment'])
                    time_str = log['timestamp'][:19].replace("T", " ")
                    st.markdown(f"""
                    <div class="violation-card">
                        <b>{log['worker_id']}</b><br>
                        ⏱ {time_str}<br>
                        ⚠️ <b>Missing:</b> {missing}<br>
                        <i>Confidence: {log['confidence_score']:.2f}</i>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.error("Failed to load the selected image.")
    else:
        # Determine source type
        src = 0 if "0" in video_source else video_source
        cap = cv2.VideoCapture(src)
        
        while run and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                st.warning("Video stream disconnected or ended.")
                break
                
            # 1. Process Frame
            processed_frame = detector.process_frame(frame)
            frame_rgb = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
            
            # 2. Render Frame
            frame_placeholder.image(frame_rgb, channels="RGB", use_container_width=True)
            
            # 3. Process MQTT Queue for New Alerts
            while not st.session_state.mqtt_queue.empty():
                alert = st.session_state.mqtt_queue.get()
                st.session_state.logs.insert(0, alert)
                if len(st.session_state.logs) > 50:  # keep history manageable
                    st.session_state.logs.pop()
                    
            # 4. Render Logs
            with log_placeholder.container():
                if not st.session_state.logs:
                    st.markdown('<p class="compliant-text">✅ No violations detected yet. All workers are compliant.</p>', unsafe_allow_html=True)
                for log in st.session_state.logs:
                    missing = ", ".join(log['missing_equipment'])
                    time_str = log['timestamp'][:19].replace("T", " ")
                    st.markdown(f"""
                    <div class="violation-card">
                        <b>{log['worker_id']}</b><br>
                        ⏱ {time_str}<br>
                        ⚠️ <b>Missing:</b> {missing}<br>
                        <i>Confidence: {log['confidence_score']:.2f}</i>
                    </div>
                    """, unsafe_allow_html=True)
                    
        cap.release()
else:
    frame_placeholder.info("Click 'Start Surveillance' to begin live monitoring.")
    with log_placeholder.container():
        if not st.session_state.logs:
            st.markdown('<p class="compliant-text">✅ No violations detected yet. All workers are compliant.</p>', unsafe_allow_html=True)
        for log in st.session_state.logs:
            missing = ", ".join(log['missing_equipment'])
            time_str = log['timestamp'][:19].replace("T", " ")
=======
>>>>>>> 23bb9ced683c99cd7b7cc1433e6c86b5f075baf1
            st.markdown(f"""
<div class="violation-card">
  <div class="worker-id">🚨 {wid} — {zone}</div>
  <div><small>🕐 {ts}</small></div>
  <div class="missing-ppe">✗ Missing: {missing or "—"}</div>
  <div class="present-ppe">✓ Present: {present or "—"}</div>
  <small>Confidence: {conf:.0%}</small>
</div>""", unsafe_allow_html=True)

        if st.button("🗑️ Clear violations"):
            st.session_state.logs = []
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Event History
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📋 Event History":
    st.title("📋 Event History")

    history = list(st.session_state.event_history)

    col_s, col_f = st.columns([2, 1])
    with col_s:
        search = st.text_input("🔍 Search (worker ID, zone, missing PPE)", "")
    with col_f:
        zone_filter = st.selectbox(
            "Filter by zone",
            ["All"] + list(config.ZONE_RULES.keys()),
            format_func=lambda z: "All" if z == "All" else z.replace("_", " ").title(),
        )

    if search:
        history = [e for e in history if search.lower() in json.dumps(e).lower()]
    if zone_filter != "All":
        history = [e for e in history if e.get("zone") == zone_filter]

    st.markdown(f"**{len(history)} events**")

    if not history:
        st.info("No events match the current filter.")
    else:
        for ev in history[:100]:
            ts      = ev.get("timestamp", "—")
            wid     = ev.get("worker_id", "—")
            zone    = ev.get("zone", "—").replace("_", " ").title()
            missing = ", ".join(ev.get("missing_ppe", [])) or "None"
            with st.expander(f"🚨 {wid} | {zone} | {ts[:19] if ts != '—' else '—'}"):
                st.json(ev)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Worker Compliance
# ══════════════════════════════════════════════════════════════════════════════

elif page == "👷 Worker Compliance":
    st.title("👷 Worker Compliance")

    stats = st.session_state.worker_stats
    if not stats:
        st.info("No worker data yet. Start Live Monitoring to populate this page.")
    else:
        st.markdown(f"**{len(stats)} tracked workers**")
        for wid, s in stats.items():
            violations = s["violations"]
            last_seen  = s["last_seen"] or "—"
            colour     = "violation-card" if violations > 0 else "compliant-card"
            st.markdown(f"""
<div class="{colour}">
  <div class="worker-id">👷 {wid}</div>
  <div>Total violations: <strong>{violations}</strong></div>
  <div>Last seen: <small>{last_seen[:19] if last_seen != '—' else '—'}</small></div>
</div>""", unsafe_allow_html=True)

    if st.button("Reset worker stats"):
        st.session_state.worker_stats = defaultdict(
            lambda: {"violations": 0, "frames": 0, "last_seen": None}
        )
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Zone Configuration
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🗺️ Zone Configuration":
    st.title("🗺️ Zone Configuration")
    st.info("Configure which PPE items are required in each safety zone.")

    engine = _get_rule_engine()
    zones  = engine.list_zones()

    for z in zones:
        with st.expander(f"🗺️ {z['name'].replace('_', ' ').title()}"):
            st.markdown(f"**Required PPE:** {', '.join(z['required_ppe'])}")
            new_ppe = st.multiselect(
                "Update required PPE",
                options=["helmet", "vest", "boots", "safety_belt", "lanyard", "hook", "anchor_point"],
                default=list(z["required_ppe"]),
                key=f"zone_{z['name']}",
            )
            if st.button("Save", key=f"save_{z['name']}"):
                engine.add_zone(z["name"], set(new_ppe))
                st.success(f"Zone '{z['name']}' updated.")

    st.divider()
    st.subheader("Add new zone")
    new_zone_name = st.text_input("Zone name (e.g. warehouse)")
    new_zone_ppe  = st.multiselect(
        "Required PPE",
        options=["helmet", "vest", "boots", "safety_belt", "lanyard", "hook", "anchor_point"],
    )
    if st.button("Add zone") and new_zone_name:
        engine.add_zone(new_zone_name.lower().replace(" ", "_"), set(new_zone_ppe))
        st.success(f"Zone '{new_zone_name}' added.")
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Camera Management
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📹 Camera Management":
    st.title("📹 Camera Management")

    cameras = st.session_state.cameras
    st.markdown(f"**{len(cameras)} registered camera(s)**")

    for cam in cameras:
        with st.expander(f"📹 {cam['name']} — source: {cam['source']}"):
            st.write(f"ID: `{cam['id']}`")
            st.write(f"Source: `{cam['source']}`")

    st.divider()
    st.subheader("Add camera")
    with st.form("add_camera"):
        cam_name   = st.text_input("Camera name", placeholder="Main entrance")
        cam_source = st.text_input("Source (index or URL)", placeholder="0 or rtsp://…")
        submitted  = st.form_submit_button("Add camera")
        if submitted and cam_name and cam_source:
            try:
                src = int(cam_source)
            except ValueError:
                src = cam_source
            cam_id = f"cam_{len(cameras)}"
            st.session_state.cameras.append({"id": cam_id, "name": cam_name, "source": src})
            st.success(f"Camera '{cam_name}' added (ID: {cam_id})")
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Reports
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📊 Reports":
    st.title("📊 Safety Reports")

    history  = list(st.session_state.event_history)
    now_utc  = datetime.now(timezone.utc)

    daily   = [e for e in history if _within(e.get("timestamp"), now_utc, hours=24)]
    weekly  = [e for e in history if _within(e.get("timestamp"), now_utc, hours=168)]
    monthly = [e for e in history if _within(e.get("timestamp"), now_utc, hours=720)]

    c1, c2, c3 = st.columns(3)
    c1.metric("Today",       len(daily))
    c2.metric("This week",   len(weekly))
    c3.metric("This month",  len(monthly))

    st.subheader("Violations by missing PPE (all time)")
    ppe_counts: dict[str, int] = defaultdict(int)
    for ev in history:
        for item in ev.get("missing_ppe", []):
            ppe_counts[item] += 1
    if ppe_counts:
        st.bar_chart(ppe_counts)
    else:
        st.info("No data yet.")

    st.subheader("Violations by zone (all time)")
    zone_counts: dict[str, int] = defaultdict(int)
    for ev in history:
        zone_counts[ev.get("zone", "unknown")] += 1
    if zone_counts:
        st.bar_chart(zone_counts)

    st.subheader("Top offenders")
    worker_v: dict[str, int] = defaultdict(int)
    for ev in history:
        worker_v[ev.get("worker_id", "?")] += 1
    if worker_v:
        top = sorted(worker_v.items(), key=lambda x: x[1], reverse=True)[:10]
        for wid, count in top:
            st.markdown(f"- **{wid}**: {count} violation(s)")
    else:
        st.info("No violation data yet.")


def _within(ts_str: str | None, now: datetime, hours: int) -> bool:
    if not ts_str:
        return False
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return (now - ts) <= timedelta(hours=hours)
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Model Monitoring
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🤖 Model Monitoring":
    st.title("🤖 Model Monitoring")

    fps_history = list(st.session_state.fps_history)
    avg_fps     = sum(fps_history) / len(fps_history) if fps_history else 0.0
    model_path  = config.DEFAULT_MODEL_PATH
    model_exists = os.path.exists(model_path)

    c1, c2, c3 = st.columns(3)
    c1.metric("Model",     st.session_state.model_version)
    c2.metric("Avg FPS",   f"{avg_fps:.1f}")
    c3.metric("mAP50",     st.session_state.model_map50 or "—")

    st.subheader("Model status")
    if model_exists:
        size_mb = os.path.getsize(model_path) / 1e6
        st.success(f"✅ Custom model loaded: `{model_path}` ({size_mb:.1f} MB)")
    else:
        st.warning(f"⚠️ Custom model not found at `{model_path}`. Using fallback `{config.FALLBACK_MODEL_PATH}`.")

    if fps_history:
        st.subheader("FPS history (last 60 frames)")
        st.line_chart(fps_history)

    st.subheader("Inference settings")
    st.json({
        "detection_conf":        config.DETECTION_CONF,
        "temporal_window":       config.TEMPORAL_WINDOW,
        "temporal_min_hits":     config.TEMPORAL_MIN_HITS,
        "temporal_min_conf":     config.TEMPORAL_MIN_CONF,
        "temporal_min_zone_secs":config.TEMPORAL_MIN_ZONE_SECS,
        "tracker":               config.TRACKER_CONFIG,
    })

    st.subheader("Zone rules")
    engine = _get_rule_engine()
    for z in engine.list_zones():
        st.markdown(f"- **{z['name']}**: {', '.join(z['required_ppe'])}")
