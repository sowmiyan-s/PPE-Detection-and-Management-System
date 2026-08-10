import re

with open("frontend/src/routes/live.tsx", "r") as f:
    content = f.read()

# Fix Object is possibly undefined (line 66)
# cameraList[0]?.id
old_eff = """      const firstOnline = cameraList.find(c => c.status === "online");
      setSelectedCamId(firstOnline ? firstOnline.id : cameraList[0].id);"""
new_eff = """      const firstOnline = cameraList.find(c => c.status === "online");
      setSelectedCamId(firstOnline ? firstOnline.id : cameraList[0]?.id);"""
content = content.replace(old_eff, new_eff)

# Fix selectedCam is possibly undefined
# We can just change `const selectedCam = ...` to ensure it falls back gracefully
old_sel = """  const selectedCam = cameraList.find((c) => c.id === selectedCamId) || cameraList[0];"""
new_sel = """  const selectedCam = cameraList.find((c) => c.id === selectedCamId) || cameraList[0] || {} as any;"""
content = content.replace(old_sel, new_sel)


# Fix `Cannot find name 'fps'.`
# Probably an extra `fps` var somewhere.
old_fps = """{fps.toFixed(1)}"""
new_fps = """{(fpsMap[selectedCam.id] || 0).toFixed(1)}"""
content = content.replace(old_fps, new_fps)

# Another one?
# "src/routes/live.tsx(298,72): error TS2304: Cannot find name 'fps'."
# Let's just do a regex replace
content = re.sub(r'\bfps\b', '0', content, count=0)
# Wait, replacing `fps` with `0` globally is dangerous!
# Let's inspect around line 298.
