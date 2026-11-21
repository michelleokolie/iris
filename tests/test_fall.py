import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hw"))

from fall import FallDetector

STILL = (0, 0, 1)
FREE = (0, 0, 0.1)
HIT = (0, 0, 3.5)


def run(samples):
    d = FallDetector()
    return [t for t, xyz in samples if d.update(t, xyz)]


def test_freefall_then_impact_is_fall():
    assert run([(0, STILL), (1, FREE), (1.3, HIT)]) == [1.3]


def test_impact_without_freefall_is_not_fall():
    assert run([(0, STILL), (1, HIT)]) == []


def test_impact_after_window_is_not_fall():
    assert run([(0, FREE), (2, HIT)]) == []


def test_fires_once():
    assert run([(0, FREE), (0.2, HIT), (0.3, HIT)]) == [0.2]
