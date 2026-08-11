import os
import sys
import time
import numpy as np

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def test_reid_gallery():
    print("--- Testing WorkerReIDGallery ---")
    from src.core.worker_tracker import WorkerReIDGallery
    gallery = WorkerReIDGallery(ttl_seconds=1800.0, match_threshold=0.65)

    # Create dummy person image frame
    frame1 = np.zeros((480, 640, 3), dtype=np.uint8)
    frame1[100:300, 200:300] = [120, 50, 200] # Upper body blue/purple
    frame1[300:450, 200:300] = [30, 180, 50]  # Lower body green

    box1 = [200, 100, 300, 450]
    wid1 = gallery.match_or_register(1, frame1, box1, time.time())
    print(f"Registered initial Worker-1, returned ID: {wid1}")
    assert wid1 == 1, "Worker-1 initial registration failed"

    # Simulate worker leaving frame and returning 5 minutes later with slight scale/shift
    frame2 = np.zeros((480, 640, 3), dtype=np.uint8)
    frame2[80:280, 250:350] = [118, 52, 198]  # Very similar blue/purple shirt
    frame2[280:430, 250:350] = [32, 178, 48]  # Very similar green pants
    box2 = [250, 80, 350, 430]

    # ByteTrack would assign synthetic ID 5 after long absence
    synthetic_id = 5
    matched_id = gallery.match_or_register(synthetic_id, frame2, box2, time.time() + 300.0)
    print(f"Re-entry after 5 mins: ByteTrack assigned ID {synthetic_id} -> ReID Gallery re-assigned ID: {matched_id}")
    assert matched_id == 1, f"Re-ID failed! Expected 1, got {matched_id}"
    print("SUCCESS: 5-minute Worker Re-ID verified!\n")

def test_violation_deduplication():
    print("--- Testing Violation Deduplication ---")
    import asyncio
    from src.core import db

    async def _run():
        wid = "WORKER-TEST-99"
        missing = ["helmet", "vest"]
        
        id1 = await db.record_violation(
            worker_id=wid,
            zone_id="general_plant",
            violation_type="Missing helmet, vest",
            detected_ppe=[],
            missing_ppe=missing,
            confidence=0.92
        )
        print(f"First active violation recorded ID: {id1}")

        # Record same violation again for same worker
        id2 = await db.record_violation(
            worker_id=wid,
            zone_id="general_plant",
            violation_type="Missing helmet, vest",
            detected_ppe=[],
            missing_ppe=missing,
            confidence=0.95
        )
        print(f"Second active violation recorded ID: {id2}")
        assert id1 == id2, f"Deduplication failed! Expected same ID {id1}, got {id2}"

        # Clean up test violation
        await db.delete_violation(id1)
        print("SUCCESS: Active Violation Deduplication verified!\n")

    asyncio.run(_run())

if __name__ == "__main__":
    test_reid_gallery()
    test_violation_deduplication()
    print("ALL CORE VERIFICATION TESTS PASSED SUCCESSFULLY!")
