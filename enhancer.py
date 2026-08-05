import cv2
import time
import numpy as np

class IndustrialImageEnhancer:
    def __init__(self, clip_limit=2.5, tile_grid_size=(8, 8)):
        """
        Initialize the IndustrialImageEnhancer.
        Args:
            clip_limit (float): Threshold for contrast limiting.
            tile_grid_size (tuple): Size of grid for histogram equalization.
        """
        self.clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)

    def enhance(self, frame: np.ndarray) -> np.ndarray:
        """
        Enhances the input BGR frame for low-light and dust conditions using CLAHE on the L channel.
        Args:
            frame (np.ndarray): Input BGR image.
        Returns:
            np.ndarray: Enhanced BGR image.
        """
        # Convert BGR to LAB color space
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        
        # Split the channels (Luminance, A, B)
        l_channel, a_channel, b_channel = cv2.split(lab)
        
        # Apply CLAHE to the L-channel
        cl = self.clahe.apply(l_channel)
        
        # Merge the CLAHE enhanced L-channel back with A and B channels
        merged_lab = cv2.merge((cl, a_channel, b_channel))
        
        # Convert LAB back to BGR
        enhanced_bgr = cv2.cvtColor(merged_lab, cv2.COLOR_LAB2BGR)
        
        return enhanced_bgr

if __name__ == "__main__":
    # Basic performance test
    enhancer = IndustrialImageEnhancer()
    # Create a dummy 1080p frame
    dummy_frame = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
    
    # Warmup
    _ = enhancer.enhance(dummy_frame)
    
    # Test performance
    start_time = time.perf_counter()
    for _ in range(100):
        _ = enhancer.enhance(dummy_frame)
    end_time = time.perf_counter()
    
    avg_time_ms = ((end_time - start_time) / 100) * 1000
    print(f"Average processing time per 1080p frame: {avg_time_ms:.2f} ms")
