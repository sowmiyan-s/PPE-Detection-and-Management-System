import streamlit as st
import cv2
import json
import paho.mqtt.client as mqtt
from queue import Queue
from detector import PPEDetector

# Page Config
st.set_page_config(page_title="PPE Compliance Dashboard", page_icon="👷", layout="wide")

# Custom CSS for modern design and violation cards
st.markdown("""
<style>
.violation-card {
    background-color: #ff4b4b;
    color: white;
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 10px;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.2);
}
.compliant-text {
    color: #4CAF50;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

st.title("🏭 Real-Time Worker PPE Compliance System")

# Initialize Session State
if "logs" not in st.session_state:
    st.session_state.logs = []
if "mqtt_queue" not in st.session_state:
    st.session_state.mqtt_queue = Queue()

MQTT_BROKER = "test.mosquitto.org"
MQTT_PORT = 1883
MQTT_TOPIC = "factory/ppe_violations"

# MQTT Callback
def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        st.session_state.mqtt_queue.put(payload)
    except:
        pass

@st.cache_resource
def get_mqtt_client():
    client = mqtt.Client(protocol=mqtt.MQTTv311)
    client.on_message = on_message
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.subscribe(MQTT_TOPIC)
        client.loop_start()
        return client
    except Exception as e:
        return None

# Start MQTT Client
client = get_mqtt_client()
if client is None:
    st.sidebar.error("Failed to connect to MQTT Broker.")

import os

@st.cache_resource
def get_detector():
    trained_model = "runs/detect/train/weights/best.pt"
    if os.path.exists(trained_model):
        st.sidebar.success(f"Loaded custom model: {trained_model}")
        return PPEDetector(model_path=trained_model, mqtt_broker=MQTT_BROKER, mqtt_port=MQTT_PORT)
    else:
        st.sidebar.warning(f"Custom model '{trained_model}' not found. Falling back to generic YOLOv8n.")
        return PPEDetector(model_path="yolov8n.pt", mqtt_broker=MQTT_BROKER, mqtt_port=MQTT_PORT)

# UI Layout
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Live Surveillance Feed")
    
    # Input options
    video_source = st.selectbox("Select Video Source", ["0 (Webcam)", "rtsp://simulated.stream", "simulated.mp4"])
    run = st.checkbox("▶️ Start Surveillance", value=False)
    
    # Placeholders for video and metrics
    frame_placeholder = st.empty()

with col2:
    st.subheader("🚨 Real-Time Violation Alerts")
    log_placeholder = st.empty()
    
    if st.button("Clear Logs"):
        st.session_state.logs = []

if run:
    detector = get_detector()
    
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
            st.markdown(f"""
            <div class="violation-card">
                <b>{log['worker_id']}</b><br>
                ⏱ {time_str}<br>
                ⚠️ <b>Missing:</b> {missing}<br>
                <i>Confidence: {log['confidence_score']:.2f}</i>
            </div>
            """, unsafe_allow_html=True)
