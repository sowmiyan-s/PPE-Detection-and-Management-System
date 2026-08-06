"""Tests for Stage-3 person-to-PPE association."""

import pytest
from association import associate_ppe_to_persons, get_intersection_over_area


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _person(pid: int, x1=0, y1=0, x2=100, y2=200):
    return {"id": pid, "box": [float(x1), float(y1), float(x2), float(y2)], "class_name": "person"}


def _ppe(cls: str, x1=0, y1=0, x2=50, y2=50, conf=0.9):
    return {"box": [float(x1), float(y1), float(x2), float(y2)],
            "class_name": cls, "confidence": conf}


# ── get_intersection_over_area ────────────────────────────────────────────────

def test_full_overlap():
    box = [0.0, 0.0, 100.0, 100.0]
    assert get_intersection_over_area(box, box) == pytest.approx(1.0, abs=0.01)


def test_no_overlap():
    box_a = [0.0, 0.0, 50.0, 50.0]
    box_b = [60.0, 60.0, 100.0, 100.0]
    assert get_intersection_over_area(box_a, box_b) == 0.0


def test_partial_overlap():
    box_a = [0.0, 0.0, 100.0, 100.0]
    box_b = [50.0, 0.0, 150.0, 100.0]   # 50 % overlap on x-axis
    result = get_intersection_over_area(box_b, box_a)
    assert 0.3 < result < 0.6


# ── associate_ppe_to_persons ──────────────────────────────────────────────────

def test_no_persons_returns_empty():
    ppe = [_ppe("helmet", 10, 0, 40, 30)]
    result = associate_ppe_to_persons([], ppe)
    assert result == {}


def test_no_ppe_returns_empty_lists():
    persons = [_person(1)]
    result = associate_ppe_to_persons(persons, [])
    assert result == {1: []}


def test_helmet_on_head_assigned():
    """Helmet positioned in upper body region should be assigned to the person."""
    person  = _person(1, x1=0, y1=0, x2=100, y2=200)
    helmet  = _ppe("helmet", x1=10, y1=5, x2=80, y2=45)   # top 25 % of person
    result  = associate_ppe_to_persons([person], [helmet])
    assert result[1][0]["class_name"] == "helmet"


def test_boots_at_feet_assigned():
    """Boots at the bottom of the person box should be assigned correctly."""
    person = _person(1, x1=0, y1=0, x2=100, y2=200)
    boots  = _ppe("boots", x1=10, y1=155, x2=90, y2=195)  # foot region
    result = associate_ppe_to_persons([person], [boots])
    assert result[1][0]["class_name"] == "boots"


def test_ppe_outside_all_persons_uses_nearest():
    """PPE completely outside person boxes falls back to nearest person."""
    person = _person(1, x1=0, y1=0, x2=100, y2=200)
    vest   = _ppe("vest", x1=110, y1=50, x2=160, y2=100)   # outside but close
    result = associate_ppe_to_persons([person], [vest], max_distance_px=200.0)
    assert result[1][0]["class_name"] == "vest"


def test_two_persons_each_get_own_ppe():
    """Each PPE item should be assigned to the nearest/containing person."""
    p1 = _person(1, x1=0,   y1=0, x2=100, y2=200)
    p2 = _person(2, x1=200, y1=0, x2=300, y2=200)
    h1 = _ppe("helmet", x1=10,  y1=5, x2=80, y2=45)   # near p1 head
    h2 = _ppe("vest",   x1=210, y1=80, x2=290, y2=140) # near p2 torso
    result = associate_ppe_to_persons([p1, p2], [h1, h2])
    assert any(i["class_name"] == "helmet" for i in result[1])
    assert any(i["class_name"] == "vest"   for i in result[2])


def test_result_keys_match_person_ids():
    persons = [_person(10), _person(20), _person(30)]
    result  = associate_ppe_to_persons(persons, [])
    assert set(result.keys()) == {10, 20, 30}
