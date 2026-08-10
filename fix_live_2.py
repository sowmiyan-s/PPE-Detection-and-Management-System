import re

with open("frontend/src/routes/live.tsx", "r") as f:
    content = f.read()

# Fix the state variables
old_state = """  const [frame, setFrame] = useState<string | null>(null);
  const [workers, setWorkers] = useState<WorkerState[]>([]);
  const [fps, setFps] = useState<number>(0);
  const [zone, setZone] = useState<string>("");"""

new_state = """  const [frames, setFrames] = useState<Record<string, string>>({});
  const [workers, setWorkers] = useState<WorkerState[]>([]);
  const [fpsMap, setFpsMap] = useState<Record<string, number>>({});
  const [zone, setZone] = useState<string>("");"""

content = content.replace(old_state, new_state)

with open("frontend/src/routes/live.tsx", "w") as f:
    f.write(content)
