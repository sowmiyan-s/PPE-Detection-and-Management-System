"""
Persistent Worker Tracker — majority-voting PPE state across frames.

Instead of trusting each individual frame's detections, this module maintains
a sliding window of PPE observations per tracked worker ID.  A PPE item is
only considered "detected" if it appeared in at least WORKER_TRACKER_MIN_VOTES
of the last WORKER_TRACKER_WINDOW frames.

This eliminates the flickering problem where a worker's compliance status
bounces between compliant/violation on every other frame.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional

from src.core import config


# ── Positive PPE classes (the ones that satisfy zone requirements) ────────────
POSITIVE_PPE: set[str] = {
    "Hard_hat", "Vest", "Glove", "Boots", "Glass", "Ear-Protection", "Mask",
    "Circular_Saw", "Fire_Extinguisher", "Fire_prevention_Net", "Welding_Equipment",
    "helmet", "vest", "gloves", "boots", "goggles", "ear-mufs", "face-guard", "safety-suit",
}

# Negative classes map to their positive counterpart
NEGATIVE_TO_POSITIVE: dict[str, str] = {
    "No-Helmet":         "Hard_hat",
    "no-helmet":         "helmet",
    "No-Vest":           "Vest",
    "no-vest":           "vest",
    "No-Glove":          "Glove",
    "no-gloves":         "gloves",
    "No-Boots":          "Boots",
    "no-boots":          "boots",
    "No-Glass":          "Glass",
    "no-goggles":        "goggles",
    "No-Ear-Protection": "Ear-Protection",
    "No-Mask":           "Mask",
}


@dataclass
class _TrackedWorker:
    """Per-worker sliding window state."""
    # Each entry is a set of PPE class names detected in that frame
    ppe_history: deque = field(
        default_factory=lambda: deque(maxlen=config.WORKER_TRACKER_WINDOW)
    )
    # Each entry is a set of negative class names detected in that frame
    neg_history: deque = field(
        default_factory=lambda: deque(maxlen=config.WORKER_TRACKER_WINDOW)
    )
    last_seen_frame: int = 0


class WorkerTracker:
    """
    Maintains persistent per-worker PPE detection state across frames.

    Usage
    -----
    tracker = WorkerTracker()

    # Each frame:
    smoothed_detected, smoothed_missing = tracker.update(
        worker_id=101,
        raw_detected={"helmet", "no-vest", "vest"},
        frame_number=42,
    )
    """

    def __init__(self) -> None:
        self._workers: dict[int, _TrackedWorker] = {}
        self._frame_count: int = 0

    def update(
        self,
        worker_id: int,
        raw_detected: set[str],
        required_ppe: set[str],
    ) -> tuple[set[str], set[str]]:
        """
        Feed one frame's raw detections for a worker.

        Parameters
        ----------
        worker_id    : ByteTrack persistent ID
        raw_detected : raw set of class names from YOLO for this worker
        required_ppe : set of PPE items required by the zone

        Returns
        -------
        (smoothed_detected, smoothed_missing)
            smoothed_detected : positive PPE items confirmed via majority vote
            smoothed_missing  : required items NOT confirmed
        """
        self._frame_count += 1
        worker = self._get_or_create(worker_id)
        worker.last_seen_frame = self._frame_count

        # Split raw detections into positive and negative
        positives = raw_detected & POSITIVE_PPE
        negatives = {cls for cls in raw_detected if cls in NEGATIVE_TO_POSITIVE}

        worker.ppe_history.append(positives)
        worker.neg_history.append(negatives)

        # Majority voting: count how many frames each PPE appeared in
        min_votes = config.WORKER_TRACKER_MIN_VOTES
        ppe_counts: dict[str, int] = defaultdict(int)
        neg_counts: dict[str, int] = defaultdict(int)

        for frame_ppes in worker.ppe_history:
            for ppe in frame_ppes:
                ppe_counts[ppe] += 1

        for frame_negs in worker.neg_history:
            for neg in frame_negs:
                neg_counts[neg] += 1

        # A PPE is "confirmed detected" if it has enough votes
        confirmed_detected: set[str] = set()
        for ppe, count in ppe_counts.items():
            if count >= min_votes:
                confirmed_detected.add(ppe)

        # A negative class overrides the positive ONLY if the negative has
        # more votes than the positive (e.g., no-helmet seen 7/10, helmet seen 2/10)
        for neg_cls, pos_cls in NEGATIVE_TO_POSITIVE.items():
            neg_vote = neg_counts.get(neg_cls, 0)
            pos_vote = ppe_counts.get(pos_cls, 0)
            if neg_vote > pos_vote and pos_cls in confirmed_detected:
                confirmed_detected.discard(pos_cls)

        # Missing = required but not confirmed
        smoothed_missing = required_ppe - confirmed_detected

        return confirmed_detected, smoothed_missing

    def cleanup_stale(self) -> list[int]:
        """Remove workers not seen for WORKER_TRACKER_STALE_FRAMES. Returns removed IDs."""
        stale_threshold = self._frame_count - config.WORKER_TRACKER_STALE_FRAMES
        stale_ids = [
            wid for wid, w in self._workers.items()
            if w.last_seen_frame < stale_threshold
        ]
        for wid in stale_ids:
            del self._workers[wid]
        return stale_ids

    def get_confirmed_ppe(self, worker_id: int) -> set[str]:
        """Get the current majority-voted PPE set for a worker."""
        worker = self._workers.get(worker_id)
        if worker is None:
            return set()

        min_votes = config.WORKER_TRACKER_MIN_VOTES
        ppe_counts: dict[str, int] = defaultdict(int)
        for frame_ppes in worker.ppe_history:
            for ppe in frame_ppes:
                ppe_counts[ppe] += 1

        return {ppe for ppe, count in ppe_counts.items() if count >= min_votes}

    # ── Internal ───────────────────────────────────────────────────────────────

    def _get_or_create(self, worker_id: int) -> _TrackedWorker:
        if worker_id not in self._workers:
            self._workers[worker_id] = _TrackedWorker()
        return self._workers[worker_id]


# ── Persistent Visual Re-Identification Gallery ───────────────────────────────

import cv2
import numpy as np

class WorkerReIDGallery:
    """
    Visual feature gallery to re-identify workers who exit and re-enter the scene
    after long periods (e.g. 5–30 minutes). Maintains spatial color signatures per worker ID.
    """
    def __init__(self, ttl_seconds: float = 1800.0, match_threshold: float = 0.68) -> None:
        self.ttl_seconds = ttl_seconds
        self.match_threshold = match_threshold
        self._signatures: dict[int, dict] = {}  # worker_id -> {"sig": np.ndarray, "last_seen": float}

    @staticmethod
    def extract_signature(frame: np.ndarray, box: list[float]) -> np.ndarray | None:
        """Extract a 3-region spatial HSV color histogram signature for a person box."""
        if frame is None or len(box) < 4:
            return None
        h, w = frame.shape[:2]
        x1 = max(0, min(w - 1, int(box[0])))
        y1 = max(0, min(h - 1, int(box[1])))
        x2 = max(x1 + 1, min(w, int(box[2])))
        y2 = max(y1 + 1, min(h, int(box[3])))

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0 or crop.shape[0] < 10 or crop.shape[1] < 10:
            return None

        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        crop_h = hsv.shape[0]
        
        # Divide into 3 vertical zones: Upper torso, Middle body, Lower body
        zone1 = hsv[0 : int(crop_h * 0.35), :]
        zone2 = hsv[int(crop_h * 0.35) : int(crop_h * 0.70), :]
        zone3 = hsv[int(crop_h * 0.70) :, :]

        hist_parts = []
        for z in [zone1, zone2, zone3]:
            if z.size > 0:
                h_hist = cv2.calcHist([z], [0, 1], None, [12, 8], [0, 180, 0, 256])
                cv2.normalize(h_hist, h_hist)
                hist_parts.append(h_hist.flatten())
            else:
                hist_parts.append(np.zeros(96, dtype=np.float32))

        # Add aspect ratio feature
        aspect_ratio = np.array([(y2 - y1) / float(max(1, x2 - x1))], dtype=np.float32)
        
        sig = np.concatenate([*hist_parts, aspect_ratio])
        norm = np.linalg.norm(sig)
        if norm > 1e-6:
            sig = sig / norm
        return sig

    def match_or_register(
        self,
        worker_id: int,
        frame: np.ndarray,
        box: list[float],
        now: float,
        exclude_ids: set[int] | None = None
    ) -> int:
        """
        Check if person's visual signature matches an existing worker in gallery.
        Guarantees that no ID present in exclude_ids is reused for a different person in the same frame.
        """
        exclude = exclude_ids or set()
        sig = self.extract_signature(frame, box)
        if sig is None:
            res_id = worker_id
            while res_id in exclude:
                res_id += 1
            return res_id

        # Clean stale signatures older than ttl_seconds
        stale = [wid for wid, data in self._signatures.items() if now - data["last_seen"] > self.ttl_seconds]
        for wid in stale:
            del self._signatures[wid]

        # 1. If worker_id is already in gallery and not excluded by another person in same frame, update signature
        if worker_id in self._signatures and worker_id not in exclude:
            old_sig = self._signatures[worker_id]["sig"]
            # Smoothly update stored signature (80% old, 20% new)
            updated_sig = 0.8 * old_sig + 0.2 * sig
            norm = np.linalg.norm(updated_sig)
            if norm > 1e-6: updated_sig /= norm
            self._signatures[worker_id] = {"sig": updated_sig, "last_seen": now}
            return worker_id

        # 2. Search gallery for matching signature across non-excluded stored workers
        best_match_id = None
        best_sim = 0.0

        for stored_id, data in self._signatures.items():
            if stored_id in exclude:
                continue
            stored_sig = data["sig"]
            sim = float(np.dot(sig, stored_sig))
            if sim > best_sim:
                best_sim = sim
                best_match_id = stored_id

        if best_match_id is not None and best_sim >= self.match_threshold:
            # Match found! Re-assign worker_id to previous remembered ID
            old_sig = self._signatures[best_match_id]["sig"]
            updated_sig = 0.7 * old_sig + 0.3 * sig
            norm = np.linalg.norm(updated_sig)
            if norm > 1e-6: updated_sig /= norm
            self._signatures[best_match_id] = {"sig": updated_sig, "last_seen": now}
            return best_match_id
        else:
            # Register new worker signature with guaranteed unique ID
            res_id = worker_id
            while res_id in exclude:
                res_id += 1
            self._signatures[res_id] = {"sig": sig, "last_seen": now}
            return res_id

