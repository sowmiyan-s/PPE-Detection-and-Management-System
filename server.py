from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn
import asyncio
import cv2
import json
import base64
from vision_pipeline import VisionPipeline

app = FastAPI()

# HTML template for the live dashboard
html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Live Safety Dashboard</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: #ffffff; margin: 0; padding: 20px; }
            h1 { color: #00E676; text-align: center; margin-bottom: 30px;}
            .container { display: flex; flex-direction: row; gap: 30px; max-width: 1400px; margin: 0 auto;}
            .video-container { flex: 2; background-color: #1e1e1e; padding: 15px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);}
            .data-container { flex: 1; background-color: #1e1e1e; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); max-height: 80vh; overflow-y: auto;}
            h2 { color: #a0a0a0; margin-top: 0; border-bottom: 1px solid #333; padding-bottom: 10px;}
            img { width: 100%; border-radius: 8px; }
            .person-card { background: #2a2a2a; padding: 15px; margin-bottom: 15px; border-radius: 8px; border-left: 4px solid #00E676;}
            .person-id { font-weight: bold; font-size: 1.3em; color: #00E676; margin-bottom: 10px;}
            .ppe-list { display: flex; flex-wrap: wrap; gap: 8px; }
            .ppe-item { background: #3a3a3a; padding: 6px 12px; border-radius: 20px; font-size: 0.9em; border: 1px solid #555;}
            .missing-ppe { color: #ff5252; font-style: italic; }
        </style>
    </head>
    <body>
        <h1>Safety Monitoring System</h1>
        <div class="container">
            <div class="video-container">
                <h2>Live Camera Feed</h2>
                <img id="video_feed" src="" alt="Live Video Feed will appear here..."/>
            </div>
            <div class="data-container">
                <h2>Personnel Tracking</h2>
                <div id="tracking_data">Waiting for data...</div>
            </div>
        </div>
        <script>
            var ws = new WebSocket("ws://" + window.location.host + "/ws");
            ws.onmessage = function(event) {
                var data = JSON.parse(event.data);
                
                // Update video frame
                if (data.frame) {
                    document.getElementById('video_feed').src = "data:image/jpeg;base64," + data.frame;
                }
                
                // Update tracking data
                if (data.tracking) {
                    var container = document.getElementById('tracking_data');
                    container.innerHTML = '';
                    
                    if (data.tracking.length === 0) {
                        container.innerHTML = '<p style="color:#777;">No personnel detected in frame.</p>';
                    }
                    
                    data.tracking.forEach(function(person) {
                        var card = document.createElement('div');
                        card.className = 'person-card';
                        
                        var idTitle = document.createElement('div');
                        idTitle.className = 'person-id';
                        idTitle.textContent = "Worker ID: #" + person.person_id;
                        card.appendChild(idTitle);
                        
                        var ppeList = document.createElement('div');
                        ppeList.className = 'ppe-list';
                        if (person.equipment.length > 0) {
                            person.equipment.forEach(function(eq) {
                                var badge = document.createElement('span');
                                badge.className = 'ppe-item';
                                badge.textContent = eq;
                                ppeList.appendChild(badge);
                            });
                        } else {
                            var warning = document.createElement('span');
                            warning.className = 'missing-ppe';
                            warning.textContent = "No Safety Equipment Detected!";
                            ppeList.appendChild(warning);
                        }
                        
                        card.appendChild(ppeList);
                        container.appendChild(card);
                    });
                }
            };
            ws.onclose = function() {
                document.getElementById('tracking_data').innerHTML = '<p style="color:#ff5252;">Connection lost. Retrying...</p>';
                setTimeout(function() { window.location.reload(); }, 3000);
            };
        </script>
    </body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"Error sending message: {e}")

manager = ConnectionManager()

# Global state for pipeline and camera
pipeline = None
camera = None

async def vision_loop():
    global pipeline, camera
    # Initialize pipeline with standard YOLOv8n (default). 
    # Change to your custom model path when ready e.g., VisionPipeline("best.pt")
    pipeline = VisionPipeline("yolov8n.pt") 
    
    # 0 is the default web camera. Change to an RTSP link like 'rtsp://user:pass@ip:port' for IP cameras
    camera = cv2.VideoCapture(0) 
    
    if not camera.isOpened():
        print("Warning: Could not open camera. Please verify camera index or RTSP stream URL.")
        # Optional: could put a loop here to retry camera connection
    
    while True:
        if not camera.isOpened():
            await asyncio.sleep(1)
            continue
            
        success, frame = camera.read()
        if not success:
            await asyncio.sleep(0.1)
            continue
            
        # Optional: Resize frame to improve processing speed
        frame = cv2.resize(frame, (800, 600))
        
        # Run detection and tracking
        processed_frame, dashboard_data = pipeline.process_frame(frame)
        
        # Encode frame to base64 for fast WebSocket transmission
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 70] # Lower quality for faster streaming
        success, buffer = cv2.imencode('.jpg', processed_frame, encode_param)
        
        if success:
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            
            payload = {
                "frame": frame_base64,
                "tracking": dashboard_data
            }
            await manager.broadcast(json.dumps(payload))
        
        # Yield control back to event loop
        await asyncio.sleep(0.01)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        
@app.on_event("startup")
async def startup_event():
    # Start the vision processing loop as a background asyncio task
    asyncio.create_task(vision_loop())

@app.on_event("shutdown")
def shutdown_event():
    global camera
    if camera is not None:
        camera.release()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
