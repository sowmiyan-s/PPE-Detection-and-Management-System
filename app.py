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

Run:
    streamlit run app.py
"""

from __future__ import annotations

import json
import os
import queue
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import cv2
import paho.mqtt.client as mqtt
import streamlit as st

import config
from detector import PPEDetector
from rule_engine import RuleEngine

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="EdgeVision PPE Dashboard",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────

st.markdown("""
<style>
.violation-card {
    background: #2d1b1b; border-left: 4px solid #e53935; border-radius: 6px;
    padding: 12px; margin-bottom: 10px;
}
.compliant-card {
    background: #1b2d1b; border-left: 4px solid #43a047; border-radius: 6px;
    padding: 12px; margin-bottom: 10px;
}
.worker-id   { font-weight: 700; font-size: 1.05rem; }
.missing-ppe { color: #ef5350; font-weight: 600; }
.present-ppe { color: #66bb6a; }
</style>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────

def _init() -> None:
    defaults = {
        "logs":          [],
        "mqtt_queue":    queue.Queue(),
        "live_running":  False,
        "active_zone":   config.DEFAULT_ZONE,
        "cameras":       [{"id": "cam_0", "name": "Camera 0", "source": 0}],
        "event_history": deque(maxlen=500),
        "worker_stats":  defaultdict(lambda: {"violations": 0, "last_seen": None}),
        "fps_history":   deque(maxlen=60),
        "model_version": "yolov8n-base",
        "model_map50":   None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()

# ── MQTT ───────────────────────────────────────────────────────────────────────

def _on_mqtt_message(client, userdata, msg):
    try:
        st.session_state.mqtt_queue.put(json.loads(msg.payload.decode()))
    except Exception:
        pass

@st.cache_resource
def _get_mqtt_client():
    client = mqtt.Client(protocol=mqtt.MQTTv311)
    if config.MQTT_USERNAME:
        client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
    if config.MQTT_USE_TLS:
        client.tls_set()
    client.on_message = _on_mqtt_message
    try:
        client.connect(config.MQTT_BROKER, config.MQTT_PORT, 60)
        client.subscribe(config.MQTT_TOPIC)
        client.loop_start()
    except Exception as exc:
        st.sidebar.warning(f"MQTT unavailable: {exc}")
    return client

def _drain_queue() -> list[dict]:
    events, q = [], st.session_state.mqtt_queue
    while not q.empty():
        try:
            events.append(q.get_nowait())
        except queue.Empty:
            break
    return events

# ── Detector / rule engine ─────────────────────────────────────────────────────

@st.cache_resource
def _get_detector(zone: str = config.DEFAULT_ZONE) -> PPEDetector:
    path = config.DEFAULT_MODEL_PATH
    if not os.path.exists(path):
        path = config.FALLBACK_MODEL_PATH
    return PPEDetector(model_path=path, zone=zone)

@st.cache_resource
def _get_rule_engine() -> RuleEngine:
    return RuleEngine()

# ── Sidebar ────────────────────────────────────────────────────────────────────

_mqtt_client = _get_mqtt_client()

st.sidebar.title("🏭 EdgeVision")
st.sidebar.markdown("**PPE Compliance Platform**")
st.sidebar.divider()

page = st.sidebar.radio("Navigation", [
    "📷 Live Monitoring",
    "🚨 Active Violations",
    "📋 Event History",
    "👷 Worker Compliance",
    "🗺️ Zone Configuration",
    "📹 Camera Management",
    "📊 Reports",
    "🤖 Model Monitoring",
])

st.sidebar.divider()
st.sidebar.caption(f"MQTT: {'🟢 Connected' if _mqtt_client else '🔴 Disconnected'}")
st.sidebar.caption(f"Broker: `{config.MQTT_BROKER}:{config.MQTT_PORT}`")

# ── Drain MQTT into shared state ───────────────────────────────────────────────

for ev in _drain_queue():
    st.session_state.logs.append(ev)
    st.session_state.event_history.appendleft(ev)
    wid = ev.get("worker_id", "unknown")
    st.session_state.worker_stats[wid]["violations"] += 1
    st.session_state.worker_stats[wid]["last_seen"] = ev.get("timestamp")

if len(st.session_state.logs) > 200:
    st.session_state.logs = st.session_state.logs[-200:]

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Live Monitoring
# ══════════════════════════════════════════════════════════════════════════════

if page == "📷 Live Monitoring":
    st.title("📷 Live Monitoring")

    col_src, col_zone = st.columns([2, 1])
    with col_src:
        src_opt = st.selectbox("Camera source",
                               ["Webcam (0)", "Webcam (1)", "RTSP stream", "Video file"])
        if src_opt == "Webcam (0)":
            source = 0
        elif src_opt == "Webcam (1)":
            source = 1
        elif src_opt == "RTSP stream":
            source = st.text_input("RTSP URL", placeholder="rtsp://192.168.1.x/stream") or ""
        else:
            source = st.text_input("Video file path", placeholder="/data/footage.mp4") or ""

    with col_zone:
        zone_keys = list(config.ZONE_RULES.keys())
        active_zone = st.selectbox(
            "Active zone", options=zone_keys,
            format_func=lambda z: z.replace("_", " ").title(),
            index=zone_keys.index(config.DEFAULT_ZONE),
        )
        st.session_state.active_zone = active_zone

    run = st.checkbox("▶ Start detection", value=st.session_state.live_running)
    st.session_state.live_running = run

    frame_ph  = st.empty()
    status_ph = st.empty()

    if run and source != "":
        detector = _get_detector(active_zone)
        cap_src  = source if isinstance(source, int) else str(source)
        cap      = cv2.VideoCapture(cap_src)

        if not cap.isOpened():
            st.error(f"Cannot open camera source: {source}")
        else:
            st.info("Detection running — uncheck to stop.")
            while st.session_state.live_running:
                ok, frame = cap.read()
                if not ok:
                    st.warning("Frame read failed.")
                    break

                t0 = time.perf_counter()
                annotated, workers = detector.process_frame(frame, zone=active_zone)
                fps = 1.0 / max(time.perf_counter() - t0, 1e-6)
                st.session_state.fps_history.append(fps)

                frame_ph.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB),
                               channels="RGB", use_container_width=True)

                for ev in _drain_queue():
                    st.session_state.logs.append(ev)
                    st.session_state.event_history.appendleft(ev)

                with status_ph.container():
                    cols = st.columns(min(len(workers), 4) or 1)
                    for i, w in enumerate(workers):
                        with cols[i % len(cols)]:
                            cls  = "compliant-card" if w["compliant"] else "violation-card"
                            miss = ", ".join(w.get("missing_ppe", [])) or "—"
                            pres = ", ".join(w.get("detected_ppe", [])) or "—"
                            miss_html = (
                                "" if w["compliant"]
                                else f'<div class="missing-ppe">✗ Missing: {miss}</div>'
                            )
                            st.markdown(f"""
<div class="{cls}">
  <div class="worker-id">{w["worker_id"]}</div>
  <div>Zone: <strong>{w["zone"].replace("_"," ").title()}</strong></div>
  <div class="present-ppe">✓ {pres}</div>
  {miss_html}
  <small>conf {w.get("confidence",0):.0%} | {fps:.1f} fps</small>
</div>""", unsafe_allow_html=True)
            cap.release()
    elif run:
        st.error("Please enter a valid camera source.")
    else:
        frame_ph.info("Check 'Start detection' to begin.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Active Violations
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🚨 Active Violations":
    st.title("🚨 Active Violations")
    logs = st.session_state.logs
    if not logs:
        st.success("✅ No violations recorded yet.")
    else:
        recent = sorted(logs, key=lambda e: e.get("timestamp", ""), reverse=True)[:50]
        st.markdown(f"**{len(recent)} most recent violations**")
        for ev in recent:
            ts   = ev.get("timestamp", "—")
            wid  = ev.get("worker_id", "—")
            zone = ev.get("zone", "—").replace("_", " ").title()
            miss = ", ".join(ev.get("missing_ppe", [])) or "—"
            pres = ", ".join(ev.get("detected_ppe", [])) or "—"
            conf = ev.get("confidence", 0)
            st.markdown(f"""
<div class="violation-card">
  <div class="worker-id">🚨 {wid} — {zone}</div>
  <div><small>🕐 {ts[:19] if ts != "—" else "—"}</small></div>
  <div class="missing-ppe">✗ Missing: {miss}</div>
  <div class="present-ppe">✓ Present: {pres}</div>
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
        search = st.text_input("🔍 Search (worker ID, zone, PPE)", "")
    with col_f:
        zf = st.selectbox("Filter by zone",
                          ["All"] + list(config.ZONE_RULES.keys()),
                          format_func=lambda z: "All" if z == "All" else z.replace("_"," ").title())
    if search:
        history = [e for e in history if search.lower() in json.dumps(e).lower()]
    if zf != "All":
        history = [e for e in history if e.get("zone") == zf]
    st.markdown(f"**{len(history)} events**")
    if not history:
        st.info("No events match the current filter.")
    else:
        for ev in history[:100]:
            ts   = ev.get("timestamp", "—")
            wid  = ev.get("worker_id", "—")
            zone = ev.get("zone", "—").replace("_"," ").title()
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
            viol     = s["violations"]
            last     = s["last_seen"] or "—"
            cls      = "violation-card" if viol > 0 else "compliant-card"
            last_fmt = last[:19] if last != "—" else "—"
            st.markdown(f"""
<div class="{cls}">
  <div class="worker-id">👷 {wid}</div>
  <div>Total violations: <strong>{viol}</strong></div>
  <div>Last seen: <small>{last_fmt}</small></div>
</div>""", unsafe_allow_html=True)
    if st.button("Reset worker stats"):
        st.session_state.worker_stats = defaultdict(
            lambda: {"violations": 0, "last_seen": None})
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Zone Configuration
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🗺️ Zone Configuration":
    st.title("🗺️ Zone Configuration")
    st.info("Configure which PPE items are required in each safety zone.")
    engine = _get_rule_engine()
    for z in engine.list_zones():
        with st.expander(f"🗺️ {z['name'].replace('_',' ').title()}"):
            st.markdown(f"**Required PPE:** {', '.join(z['required_ppe'])}")
            new_ppe = st.multiselect(
                "Update required PPE",
                options=["helmet","vest","boots","safety_belt","lanyard","hook","anchor_point"],
                default=list(z["required_ppe"]),
                key=f"zone_{z['name']}",
            )
            if st.button("Save", key=f"save_{z['name']}"):
                engine.add_zone(z["name"], set(new_ppe))
                st.success(f"Zone '{z['name']}' updated.")
    st.divider()
    st.subheader("Add new zone")
    new_name = st.text_input("Zone name (e.g. warehouse)")
    new_ppe2 = st.multiselect("Required PPE",
                              options=["helmet","vest","boots","safety_belt","lanyard","hook","anchor_point"],
                              key="new_zone_ppe")
    if st.button("Add zone") and new_name:
        engine.add_zone(new_name.lower().replace(" ","_"), set(new_ppe2))
        st.success(f"Zone '{new_name}' added.")
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Camera Management
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📹 Camera Management":
    st.title("📹 Camera Management")
    cameras = st.session_state.cameras
    st.markdown(f"**{len(cameras)} registered camera(s)**")
    for cam in cameras:
        with st.expander(f"📹 {cam['name']} — {cam['source']}"):
            st.write(f"ID: `{cam['id']}` | Source: `{cam['source']}`")
    st.divider()
    st.subheader("Add camera")
    with st.form("add_camera"):
        cam_name = st.text_input("Camera name", placeholder="Main entrance")
        cam_src  = st.text_input("Source", placeholder="0 or rtsp://…")
        if st.form_submit_button("Add camera") and cam_name and cam_src:
            try:
                src = int(cam_src)
            except ValueError:
                src = cam_src
            cam_id = f"cam_{len(cameras)}"
            st.session_state.cameras.append({"id": cam_id, "name": cam_name, "source": src})
            st.success(f"Camera '{cam_name}' added.")
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Reports
# ══════════════════════════════════════════════════════════════════════════════

elif page == "📊 Reports":
    st.title("📊 Safety Reports")

    def _within(ts_str, now, hours):
        if not ts_str:
            return False
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            return (now - ts) <= timedelta(hours=hours)
        except Exception:
            return False

    history = list(st.session_state.event_history)
    now_utc = datetime.now(timezone.utc)

    c1, c2, c3 = st.columns(3)
    c1.metric("Today",      sum(1 for e in history if _within(e.get("timestamp"), now_utc, 24)))
    c2.metric("This week",  sum(1 for e in history if _within(e.get("timestamp"), now_utc, 168)))
    c3.metric("This month", sum(1 for e in history if _within(e.get("timestamp"), now_utc, 720)))

    st.subheader("Violations by missing PPE")
    ppe_c: dict[str, int] = defaultdict(int)
    for ev in history:
        for item in ev.get("missing_ppe", []):
            ppe_c[item] += 1
    if ppe_c:
        st.bar_chart(ppe_c)
    else:
        st.info("No data yet.")

    st.subheader("Violations by zone")
    zone_c: dict[str, int] = defaultdict(int)
    for ev in history:
        zone_c[ev.get("zone", "unknown")] += 1
    if zone_c:
        st.bar_chart(zone_c)

    st.subheader("Top offenders")
    worker_v: dict[str, int] = defaultdict(int)
    for ev in history:
        worker_v[ev.get("worker_id", "?")] += 1
    if worker_v:
        for wid, cnt in sorted(worker_v.items(), key=lambda x: x[1], reverse=True)[:10]:
            st.markdown(f"- **{wid}**: {cnt} violation(s)")
    else:
        st.info("No violation data yet.")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Model Monitoring
# ══════════════════════════════════════════════════════════════════════════════

elif page == "🤖 Model Monitoring":
    st.title("🤖 Model Monitoring")
    fps_hist    = list(st.session_state.fps_history)
    avg_fps     = sum(fps_hist) / len(fps_hist) if fps_hist else 0.0
    model_path  = config.DEFAULT_MODEL_PATH
    model_exists = os.path.exists(model_path)

    c1, c2, c3 = st.columns(3)
    c1.metric("Model",   st.session_state.model_version)
    c2.metric("Avg FPS", f"{avg_fps:.1f}")
    c3.metric("mAP50",   st.session_state.model_map50 or "—")

    if model_exists:
        size_mb = os.path.getsize(model_path) / 1e6
        st.success(f"✅ Custom model: `{model_path}` ({size_mb:.1f} MB)")
    else:
        st.warning(f"⚠️ Custom model not found at `{model_path}`. "
                   f"Using fallback `{config.FALLBACK_MODEL_PATH}`.")

    if fps_hist:
        st.subheader("FPS history (last 60 frames)")
        st.line_chart(fps_hist)

    st.subheader("Inference settings")
    st.json({
        "detection_conf":         config.DETECTION_CONF,
        "temporal_window":        config.TEMPORAL_WINDOW,
        "temporal_min_hits":      config.TEMPORAL_MIN_HITS,
        "temporal_min_conf":      config.TEMPORAL_MIN_CONF,
        "temporal_min_zone_secs": config.TEMPORAL_MIN_ZONE_SECS,
        "tracker":                config.TRACKER_CONFIG,
    })

    st.subheader("Zone rules")
    for z in _get_rule_engine().list_zones():
        st.markdown(f"- **{z['name']}**: {', '.join(z['required_ppe'])}")
