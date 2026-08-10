import cv2
import numpy as np
import math

width, height = 640, 480
out = cv2.VideoWriter('test_mjpg.avi', cv2.VideoWriter_fourcc(*'MJPG'), 30, (width, height))

for i in range(120): # 4 seconds of video at 30 fps
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Draw a moving circle (like a head)
    cx = int(width / 2 + math.sin(i * 0.1) * 100)
    cy = int(height / 2 + math.cos(i * 0.1) * 50)
    cv2.circle(frame, (cx, cy), 40, (0, 255, 0), -1)
    
    # Add some text
    cv2.putText(frame, f"Simulated Camera Feed {i}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    out.write(frame)

out.release()
print("Successfully generated test_mjpg.avi")
