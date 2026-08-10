import re

with open("frontend/src/routes/live.tsx", "r") as f:
    content = f.read()

# Update state variables
old_state = """  const [frame, setFrame] = useState<string | null>(null);
  const [fps, setFps] = useState(0);
  const [zone, setZone] = useState("");
  const [workers, setWorkers] = useState<Worker[]>([]);"""

new_state = """  const [frames, setFrames] = useState<Record<string, string>>({});
  const [fpsMap, setFpsMap] = useState<Record<string, number>>({});
  const [zone, setZone] = useState("");
  const [workers, setWorkers] = useState<Worker[]>([]);"""
content = content.replace(old_state, new_state)

# Update useEffect for default camera
old_useeffect = """  // Set default selected camera once we have cameras
  useEffect(() => {
    if (cameraList.length > 0 && !selectedCamId && cameraList[0]?.id) {
      setSelectedCamId(cameraList[0].id);
    }
  }, [cameraList, selectedCamId]);"""

new_useeffect = """  // Set default selected camera once we have cameras
  useEffect(() => {
    if (cameraList.length > 0 && !selectedCamId) {
      const firstOnline = cameraList.find(c => c.status === "online");
      setSelectedCamId(firstOnline ? firstOnline.id : cameraList[0].id);
    }
  }, [cameraList, selectedCamId]);"""
content = content.replace(old_useeffect, new_useeffect)

# Update ws.onmessage
old_ws = """        } else {
          // Normal frame payload
          if (d.camera_id && d.camera_id !== selectedCamIdRef.current) return;
          if (d.frame) setFrame(d.frame);
          if (d.fps !== undefined) setFps(d.fps);
          if (d.zone) setZone(d.zone);
          if (d.workers) setWorkers(d.workers);
        }"""

new_ws = """        } else {
          // Normal frame payload
          if (d.camera_id) {
            if (d.frame) setFrames(prev => ({ ...prev, [d.camera_id]: d.frame }));
            if (d.fps !== undefined) setFpsMap(prev => ({ ...prev, [d.camera_id]: d.fps }));
          }
          
          if (d.camera_id === selectedCamIdRef.current) {
            if (d.zone) setZone(d.zone);
            if (d.workers) setWorkers(d.workers);
          }
        }"""
content = content.replace(old_ws, new_ws)

# Update Grid View Rendering
old_grid_img = """                      {(isSelected || isLive) && frame ? (
                        <img
                          src={`data:image/jpeg;base64,${frame}`}"""
new_grid_img = """                      {(isSelected || isLive) && frames[cam.id] ? (
                        <img
                          src={`data:image/jpeg;base64,${frames[cam.id]}`}"""
content = content.replace(old_grid_img, new_grid_img)

# Update Focus View Rendering
old_focus_img = """              {frame ? (
                <img
                  src={`data:image/jpeg;base64,${frame}`}"""
new_focus_img = """              {frames[selectedCam.id] ? (
                <img
                  src={`data:image/jpeg;base64,${frames[selectedCam.id]}`}"""
content = content.replace(old_focus_img, new_focus_img)

# Also fix the fps display in grid
old_grid_fps = """<span className="font-semibold">{cam.targetFps} FPS</span>"""
new_grid_fps = """<span className="font-semibold">{fpsMap[cam.id] || 0} / {cam.targetFps} FPS</span>"""
content = content.replace(old_grid_fps, new_grid_fps)

# Fix the fps display in focus view
old_focus_fps = """              <span className="text-xl font-bold tracking-tight">{fps.toFixed(1)}</span>"""
new_focus_fps = """              <span className="text-xl font-bold tracking-tight">{(fpsMap[selectedCam.id] || 0).toFixed(1)}</span>"""
content = content.replace(old_focus_fps, new_focus_fps)

with open("frontend/src/routes/live.tsx", "w") as f:
    f.write(content)
