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
    "helmet", "vest", "gloves", "boots", "goggles",
    "ear-mufs", "face-guard", "safety-suit",
}

# Negative classes map to their positive counterpart
NEGATIVE_TO_POSITIVE: dict[str, str] = {
    "no-helmet":  "helmet",
    "no-vest":    "vest",
    "no-gloves":  "gloves",
    "no-boots":   "boots",
    "no-goggles": "goggles",
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
