import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hw"))

from ir_trigger import HandWave


def run(samples, cooldown_s=2.0):
    """samples: list of (time, reading). Returns times at which poll() fired."""
    clock = [0.0]
    cur = [False]
    w = HandWave(lambda: cur[0], now=lambda: clock[0], cooldown_s=cooldown_s)
    fired = []
    for t, r in samples:
        clock[0], cur[0] = t, r
        if w.poll():
            fired.append(t)
    return fired


def test_fires_once_on_rising_edge():
    assert run([(0, False), (1, True), (2, True), (3, True)]) == [1]


def test_cooldown_suppresses_second_wave():
    assert run([(0, True), (0.5, False), (1, True), (1.5, False), (3, True)]) == [0, 3]


def test_no_fire_while_low():
    assert run([(0, False), (1, False)]) == []
