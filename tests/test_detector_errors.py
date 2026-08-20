"""
Unit tests for bug fixes in src/core/detector.py
"""

import math
import numpy as np
import pytest

from src.core.detector import PPEDetector
import src.core.config as config


def test_detector_process_frame_handles_math_and_unbound_variables():
    """Verify that process_frame executes without NameErrors for math, aliases, or required_ppe."""
    detector = PPEDetector()
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    class MockBox:
        def __init__(self):
            self.cls = np.array([0, 1])
            self.xyxy = np.array([[50, 50, 200, 400], [70, 60, 120, 110]])
            self.conf = np.array([0.9, 0.85])
            self.id = np.array([1, None])

        def __len__(self):
            return 2

    class MockResult:
        def __init__(self):
            self.boxes = MockBox()

    detector.model.track = lambda *args, **kwargs: [MockResult()]

    annotated, states = detector.process_frame(frame, zone="default")
    assert isinstance(annotated, np.ndarray)
    assert len(states) == 1
    assert states[0]["worker_id"] == "Worker-1"


def test_detector_frame_skip_and_draw_ppe():
    """Verify that frame skipping and _draw_ppe work without error."""
    orig_skip = config.FRAME_SKIP_INTERVAL
    try:
        config.FRAME_SKIP_INTERVAL = 2
        detector = PPEDetector()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        class MockBox:
            def __init__(self):
                self.cls = np.array([0, 1])
                self.xyxy = np.array([[50, 50, 200, 400], [70, 60, 120, 110]])
                self.conf = np.array([0.9, 0.85])
                self.id = np.array([1, None])

            def __len__(self):
                return 2

        class MockResult:
            def __init__(self):
                self.boxes = MockBox()

        detector.model.track = lambda *args, **kwargs: [MockResult()]

        # Process frame 1
        detector.process_frame(frame, zone="default")
        # Process frame 2 (skipped)
        f2, s2 = detector.process_frame(frame, zone="default")
        assert len(s2) == 1
    finally:
        config.FRAME_SKIP_INTERVAL = orig_skip
