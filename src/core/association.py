"""
Stage 3 – Person-to-PPE association.

Associates each detected PPE item with the most likely worker using a
combination of:
  • Bounding-box containment (PPE centre inside person box)
  • Body-region mapping  (head → helmet/goggles, torso → vest/suit,
                          foot  → boots)
  • Nearest-person fallback when containment misses

This replaces the previous intersection-over-PPE-area heuristic with a more
robust approach that handles partial occlusion and camera angles better.
"""

from __future__ import annotations

from typing import Optional
from src.core import config


# ── Body-region fractions (relative to person bounding box height) ───────────

HEAD_REGION    = (0.00, 0.25)   # top 25 %
TORSO_REGION   = (0.20, 0.75)   # middle 55 %
FEET_REGION    = (0.65, 1.00)   # bottom 35 %

PPE_BODY_REGION: dict[str, tuple[float, float]] = {
    "Hard_hat":          HEAD_REGION,
    "No-Helmet":         HEAD_REGION,
    "helmet":            HEAD_REGION,
    "no-helmet":         HEAD_REGION,
    "Glass":             HEAD_REGION,
    "No-Glass":          HEAD_REGION,
    "goggles":           HEAD_REGION,
    "no-goggles":        HEAD_REGION,
    "Ear-Protection":    HEAD_REGION,
    "No-Ear-Protection": HEAD_REGION,
    "ear-mufs":          HEAD_REGION,
    "Mask":              HEAD_REGION,
    "No-Mask":           HEAD_REGION,
    "face-guard":        HEAD_REGION,
    "Vest":              TORSO_REGION,
    "No-Vest":           TORSO_REGION,
    "vest":              TORSO_REGION,
    "no-vest":           TORSO_REGION,
    "Glove":             TORSO_REGION,
    "No-Glove":          TORSO_REGION,
    "gloves":            TORSO_REGION,
    "no-gloves":         TORSO_REGION,
    "safety-suit":       TORSO_REGION,
    "Circular_Saw":      TORSO_REGION,
    "Fire_Extinguisher": TORSO_REGION,
    "Fire_prevention_Net": TORSO_REGION,
    "Welding_Equipment": TORSO_REGION,
    "Boots":             FEET_REGION,
    "No-Boots":          FEET_REGION,
    "boots":             FEET_REGION,
    "no-boots":          FEET_REGION,
}


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _box_centre(box: list[float]) -> tuple[float, float]:
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def _centre_in_box(cx: float, cy: float, box: list[float]) -> bool:
    return box[0] <= cx <= box[2] and box[1] <= cy <= box[3]


def _body_region_box(
    person_box: list[float],
    region: tuple[float, float],
) -> list[float]:
    """Return the sub-box for a vertical body region (fraction of height)."""
    x1, y1, x2, y2 = person_box
    h = y2 - y1
    return [x1, y1 + region[0] * h, x2, y1 + region[1] * h]


def _euclidean_distance(
    p1: tuple[float, float],
    p2: tuple[float, float],
) -> float:
    return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5


def _intersection_over_ppe_area(
    person_box: list[float],
    ppe_box: list[float],
) -> float:
    """Fraction of the PPE box that lies inside the person box."""
    ix1 = max(person_box[0], ppe_box[0])
    iy1 = max(person_box[1], ppe_box[1])
    ix2 = min(person_box[2], ppe_box[2])
    iy2 = min(person_box[3], ppe_box[3])

    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0

    inter_area = (ix2 - ix1 + 1) * (iy2 - iy1 + 1)
    ppe_area   = max(
        (ppe_box[2] - ppe_box[0] + 1) * (ppe_box[3] - ppe_box[1] + 1),
        1,
    )
    return inter_area / ppe_area


# ── Main association function ─────────────────────────────────────────────────

def associate_ppe_to_persons(
    persons: list[dict],
    ppe_items: list[dict],
    containment_threshold: float = None,
    max_distance_px: float = 300.0,
) -> dict[int, list[dict]]:
    """
    Associate each PPE item to a tracked person.

    Parameters
    ----------
    persons : list of dicts with keys: id, box, class_name
    ppe_items : list of dicts with keys: box, class_name, confidence
    containment_threshold : minimum overlap fraction to assign via containment
    max_distance_px : fallback nearest-person search radius (pixels)

    Returns
    -------
    dict mapping person_id → list of associated PPE dicts
    """
    threshold = containment_threshold or config.PPE_CONTAINMENT_THRESHOLD
    result: dict[int, list[dict]] = {p["id"]: [] for p in persons}

    if not persons:
        return result

    for ppe in ppe_items:
        ppe_box    = ppe["box"]
        ppe_class  = ppe["class_name"]
        cx, cy     = _box_centre(ppe_box)
        region     = PPE_BODY_REGION.get(ppe_class)

        best_person_id: Optional[int] = None
        best_score: float = -1.0

        for person in persons:
            pid  = person["id"]
            pbox = person["box"]

            # Method 1 – containment in body region
            if region is not None:
                region_box = _body_region_box(pbox, region)
                overlap    = _intersection_over_ppe_area(region_box, ppe_box)
                if overlap >= threshold and overlap > best_score:
                    best_score     = overlap
                    best_person_id = pid
                    continue

            # Method 2 – containment in full person box
            overlap = _intersection_over_ppe_area(pbox, ppe_box)
            if overlap >= threshold and overlap > best_score:
                best_score     = overlap
                best_person_id = pid

        # Method 3 – nearest-person fallback (if nothing matched via containment)
        if best_person_id is None:
            min_dist = float("inf")
            for person in persons:
                pc = _box_centre(person["box"])
                d  = _euclidean_distance((cx, cy), pc)
                if d < min_dist and d <= max_distance_px:
                    min_dist       = d
                    best_person_id = person["id"]

        if best_person_id is not None:
            result[best_person_id].append(ppe)

    return result


# ── Legacy helper (kept for backward compatibility) ───────────────────────────

def get_intersection_over_area(boxA: list[float], boxB: list[float]) -> float:
    """Intersection area divided by boxA area (original implementation)."""
    return _intersection_over_ppe_area(boxA, boxB)
