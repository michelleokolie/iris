import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hw"))

import actuate
import io_main
from actuate import Actuator
from fake_gpio import FakeGpio
from fuse import FAR_CM, MID_CM, NEAR_CM, fuse, range_level


def test_range_level_by_distance():
    assert range_level(NEAR_CM - 1, 0) == 3
    assert range_level(MID_CM - 1, 0) == 2
    assert range_level(FAR_CM - 1, 0) == 1
    assert range_level(FAR_CM + 1, 0) == 0


def test_range_level_time_to_contact():
    assert range_level(200, 200) == 3   # 1 s to contact
    assert range_level(200, 50) == 1    # 4 s to contact
    assert range_level(200, -50) == 1   # moving away


def test_no_range_passes_camera_through():
    assert fuse((2, "left"), None) == (2, "left")
    assert fuse((0, "clear"), None) == (0, "clear")


def test_ultrasonic_sets_level_camera_gives_direction():
    assert fuse((1, "left"), (NEAR_CM - 1, 0)) == (3, "left")
    assert fuse((3, "right"), (MID_CM - 1, 0)) == (2, "right")


def test_camera_alone_is_capped_at_far_when_ultrasonic_sees_nothing_near():
    assert fuse((3, "left"), (FAR_CM + 100, 0)) == (1, "left")


def test_ultrasonic_only_obstacle_is_ahead():
    assert fuse((0, "clear"), (NEAR_CM - 1, 0)) == (3, "ahead")


def test_all_clear():
    assert fuse((0, "clear"), (FAR_CM + 100, 0)) == (0, "clear")


@pytest.mark.parametrize("line", ["range", "range 50", "range 0 1", "range x 1", "range none 1", "rang 5 1"])
def test_bad_range_lines_rejected(line):
    with pytest.raises((AssertionError, ValueError)):
        io_main.parse_range(line)


def make_fusion():
    gpio, clock = FakeGpio(), [0.0]
    actuator = Actuator(gpio=gpio, sleep=lambda s: None, threaded=False)
    return io_main.Fusion(actuator, now=lambda: clock[0]), gpio, clock


def test_fusion_combines_both_sources():
    f, g, _ = make_fusion()
    f.on_line("1 left")
    assert not g.state[actuate.LED_RED]
    f.on_line("range 40.0 0.0")
    assert g.state[actuate.LED_RED]
    f.on_line("range none")
    assert not g.state[actuate.LED_RED]


def test_stale_range_expires_without_another_message():
    f, g, clock = make_fusion()
    f.on_line("range 40.0 0.0")
    assert g.state[actuate.LED_RED]
    clock[0] = io_main.RANGE_STALE_S + 0.1
    f.refresh()
    assert not g.state[actuate.LED_RED]


def test_stale_range_is_ignored():
    f, g, clock = make_fusion()
    f.on_line("range 40.0 0.0")
    assert g.state[actuate.LED_RED]
    clock[0] = io_main.RANGE_STALE_S + 0.1
    f.on_line("1 left")
    assert not g.state[actuate.LED_RED]
