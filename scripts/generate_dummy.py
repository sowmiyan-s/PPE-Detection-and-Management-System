import cv2
import numpy as np

width, height = 640, 480
out = cv2.VideoWriter('dummy_test.mp4', cv2.VideoWriter_fourcc(*'mp4v'), 30, (width, height))

for i in range(120):
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.putText(frame, f"Working Test Feed {i}", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    out.write(frame)

out.release()
print("Generated dummy_test.mp4")
