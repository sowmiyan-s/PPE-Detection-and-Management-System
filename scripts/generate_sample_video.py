"""
EdgeVision Sample Demo Video Generator
Generates a realistic test video for instant camera-less verification and Jetson benchmarking.
"""

import os
import cv2
import numpy as np

def generate_demo_video(output_path="database/evidence/sample_demo.mp4", duration_secs=8, fps=20):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    w, h = 1280, 720
    total_frames = duration_secs * fps
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (w, h))
    
    print(f"Generating synthetic demonstration video: {output_path} ({total_frames} frames)...")
    
    for i in range(total_frames):
        # Base background: factory floor gradient
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:] = (35, 40, 45) # Dark industrial steel grey
        
        # Grid lines
        for y in range(0, h, 60):
            cv2.line(frame, (0, y), (w, y), (50, 55, 60), 1)
        for x in range(0, w, 60):
            cv2.line(frame, (x, 0), (x, h), (50, 55, 60), 1)
            
        # Draw safety boundary / work zone
        cv2.rectangle(frame, (100, 100), (w - 100, h - 100), (0, 165, 255), 2)
        cv2.putText(frame, "ZONE: WORK-AT-HEIGHT & PPE MONITORING", (120, 140),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
        
        # Animate simulated worker 1 (Compliant: Hard Hat + Vest)
        w1_x = int(250 + 150 * np.sin(i * 0.05))
        w1_y = int(300 + 30 * np.cos(i * 0.05))
        
        # Worker 1 Body representation
        cv2.rectangle(frame, (w1_x, w1_y), (w1_x + 100, w1_y + 220), (180, 120, 60), -1) # Body/Torso
        cv2.circle(frame, (w1_x + 50, w1_y - 25), 30, (200, 180, 160), -1) # Head
        cv2.ellipse(frame, (w1_x + 50, w1_y - 35), (35, 18), 0, 180, 360, (0, 215, 255), -1) # Yellow Hard Hat
        cv2.rectangle(frame, (w1_x + 10, w1_y + 20), (w1_x + 90, w1_y + 120), (0, 255, 0), -1) # Green Hi-Vis Vest
        
        cv2.putText(frame, "Worker #1 (Compliant)", (w1_x - 20, w1_y - 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Animate simulated worker 2 (Non-Compliant: Missing Vest / Hard hat)
        w2_x = int(800 + 120 * np.cos(i * 0.04))
        w2_y = int(320 + 20 * np.sin(i * 0.04))
        
        cv2.rectangle(frame, (w2_x, w2_y), (w2_x + 100, w2_y + 220), (100, 80, 80), -1)
        cv2.circle(frame, (w2_x + 50, w2_y - 25), 30, (200, 180, 160), -1) # Head (No helmet)
        
        cv2.putText(frame, "Worker #2 (Violation)", (w2_x - 20, w2_y - 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    
        # Timestamp overlay
        cv2.putText(frame, f"Jetson Orin Live Demo Feed | Frame: {i:04d} | 30 FPS", (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (220, 220, 220), 2)
                    
        out.write(frame)
        
    out.release()
    print(f"[OK] Demonstration video created successfully at {output_path}")

if __name__ == "__main__":
    generate_demo_video()
