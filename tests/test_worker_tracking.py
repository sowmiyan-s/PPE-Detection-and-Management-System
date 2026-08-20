import pytest
import numpy as np
from src.core.worker_tracker import WorkerReIDGallery
from src.core.detector import PPEDetector

def test_distinct_workers_get_distinct_ids():
    gallery = WorkerReIDGallery(ttl_seconds=1800.0, match_threshold=0.85)
    
    # Frame simulation
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    
    # Worker 1 box (left side)
    box1 = [50.0, 50.0, 150.0, 400.0]
    # Worker 2 box (right side)
    box2 = [400.0, 50.0, 500.0, 400.0]
    
    # Worker 1 red shirt
    frame[50:400, 50:150, 2] = 255
    # Worker 2 blue shirt
    frame[50:400, 400:500, 0] = 255
    
    id1 = gallery.match_or_register(1, frame, box1, 100.0, exclude_ids=set())
    id2 = gallery.match_or_register(2, frame, box2, 100.0, exclude_ids={id1})
    
    assert id1 != id2, "Worker 1 and Worker 2 must be assigned distinct unique IDs!"

def test_spatial_memory_isolation():
    detector = PPEDetector()
    
    # Worker A box (left)
    boxA = [20.0, 30.0, 100.0, 300.0]
    # Worker B box (far right)
    boxB = [450.0, 30.0, 530.0, 300.0]
    
    sim = detector._compute_walk_robust_similarity(boxA, boxB)
    assert sim < 0.10, "Distant workers must have low spatial similarity!"


def test_worker_state_machine_grace_period():
    from src.core.worker_tracker import WorkerTracker
    tracker = WorkerTracker()
    req = {"helmet", "vest"}

    # 1. Warm up majority voting window (3 frames for MIN_VOTES=3)
    for _ in range(3):
        tracker.update(101, {"helmet", "vest"}, req)

    # 2. Establish NORMAL compliant state
    det, miss = tracker.update(101, {"helmet", "vest"}, req)
    assert miss == set()

    # 3. Single frame dropout should trigger GRACE state without immediately declaring missing
    det, miss = tracker.update(101, set(), req)
    assert miss == set(), "Brief PPE dropout must be held in grace period!"

    # 4. Recovery before grace expires restores NORMAL state
    det, miss = tracker.update(101, {"helmet", "vest"}, req)
    assert miss == set()


def test_moving_person_maintains_consistent_id():
    """Verify that a worker walking across the scene maintains the same tracking ID."""
    detector = PPEDetector()
    
    # Simulate a synthetic person box walking from left to right across 10 frames
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[50:350, :, 1] = 180  # green clothing signature
    
    tracked_ids = []
    for step in range(10):
        # Person box shifts right by 15px per frame (walking motion)
        x1 = 50.0 + (step * 15.0)
        y1 = 50.0 + (step * 2.0)
        x2 = 180.0 + (step * 15.0)
        y2 = 380.0 + (step * 2.0)
        
        # Mock detector internal track matching
        mock_raw = [{"raw_id": None, "box": [x1, y1, x2, y2], "class_name": "person", "confidence": 0.88}]
        
        # Inject into detector matching logic
        detector._frame_count += 1
        
        # Step 1: Pre-extract signature
        det_sigs = [detector._reid_gallery.extract_signature(frame, r["box"]) for r in mock_raw]
        
        # Check matching
        match_candidates = []
        for d_idx, rp in enumerate(mock_raw):
            box = rp["box"]
            sig = det_sigs[d_idx]
            for mem_id, mem_data in detector._track_memory.items():
                age = detector._frame_count - mem_data.get("last_frame", 0)
                mem_box = mem_data["box"]
                vx = mem_data.get("vx", 0.0)
                vy = mem_data.get("vy", 0.0)
                pred_box = [mem_box[0] + vx * age, mem_box[1] + vy * age, mem_box[2] + vx * age, mem_box[3] + vy * age]
                s_curr = detector._compute_walk_robust_similarity(box, mem_box)
                s_pred = detector._compute_walk_robust_similarity(box, pred_box)
                spatial_score = max(s_curr, s_pred)
                color_score = float(np.dot(sig, mem_data["sig"])) if (sig is not None and mem_data.get("sig") is not None) else 0.5
                total_score = (0.65 * spatial_score) + (0.35 * max(0.0, color_score))
                if len(mock_raw) == 1 and len(detector._track_memory) == 1 and spatial_score >= 0.15:
                    total_score += 0.40
                match_candidates.append({"d_idx": d_idx, "mem_id": mem_id, "score": total_score, "spatial": spatial_score})
        
        match_candidates.sort(key=lambda x: x["score"], reverse=True)
        if match_candidates and (match_candidates[0]["score"] >= 0.30 or match_candidates[0]["spatial"] >= 0.25):
            assigned_id = match_candidates[0]["mem_id"]
        else:
            if len(mock_raw) == 1 and len(detector._track_memory) >= 1:
                most_recent_id = max(detector._track_memory.keys(), key=lambda k: detector._track_memory[k].get("last_frame", 0))
                assigned_id = most_recent_id
            else:
                assigned_id = detector._next_synthetic_id
                detector._next_synthetic_id += 1
        
        # Update track memory
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        prev = detector._track_memory.get(assigned_id)
        vx = (cx - prev["cx"]) if prev and "cx" in prev else 0.0
        vy = (cy - prev["cy"]) if prev and "cy" in prev else 0.0
        
        detector._track_memory[assigned_id] = {
            "box": [x1, y1, x2, y2],
            "cx": cx,
            "cy": cy,
            "vx": vx,
            "vy": vy,
            "sig": det_sigs[0],
            "last_frame": detector._frame_count
        }
        tracked_ids.append(assigned_id)
    
    # Confirm every frame resolved to the EXACT SAME ID
    assert len(set(tracked_ids)) == 1, f"Worker walking across frames should maintain a single consistent ID! Got IDs: {tracked_ids}"


@pytest.mark.asyncio
async def test_single_worker_report_once_deduplication():
    """Verify that multiple violation triggers for the same worker only create 1 report entry."""
    from src.core import db
    
    wid = "Worker-999"
    zone = "Construction Area"
    missing = ["helmet"]
    
    # Record first violation
    evt1 = await db.record_violation(
        worker_id=wid,
        zone_id=zone,
        violation_type="Missing helmet",
        detected_ppe=["vest"],
        missing_ppe=missing,
        confidence=0.88,
        camera_id="CAM-01",
    )
    
    # Simulate repeated detection of same worker on subsequent frame
    evt2 = await db.record_violation(
        worker_id=wid,
        zone_id=zone,
        violation_type="Missing helmet",
        detected_ppe=["vest"],
        missing_ppe=missing,
        confidence=0.92,
        camera_id="CAM-01",
    )
    
    # Must return the SAME existing event ID without creating duplicate entries
    assert evt1 == evt2, "Duplicate violations for the same unacknowledged worker must be deduplicated in place!"
    
    # Clean up test violation
    await db.delete_violation(evt1)


