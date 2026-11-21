import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hw"))

import actuate
import describe
import io_main
from actuate import Actuator
from describe import Box, identify, phrase
from fake_gpio import FakeGpio

PERSON, CHAIR, UNKNOWN = 0, 56, 79


def box_for(label, real_cm, cm, x1=0.4, x2=0.6, y2=0.8):
    """A box whose height matches a real_cm-tall object seen at cm."""
    h = real_cm * describe.F_NORM / cm
    return Box(label, x1, y2 - h, x2, y2)


def test_estimated_height_matches_construction():
    assert describe.est_height_cm(box_for(PERSON, 170, 400), 400) == pytest.approx(170)


def test_label_kept_when_size_agrees():
    assert identify(box_for(PERSON, 170, 400), (400, 0)) == "person"
    assert identify(box_for(CHAIR, 90, 250), (250, 0)) == "chair"


def test_label_dropped_when_size_disagrees():
    assert identify(box_for(PERSON, 40, 300), (300, 0)) == "obstacle"   # a "person" 40 cm tall
    assert identify(box_for(CHAIR, 250, 200), (200, 0)) == "obstacle"   # a "chair" 2.5 m tall


def test_cut_off_box_only_rejected_when_too_tall():
    cut = Box(PERSON, 0.4, 0.5, 0.6, 1.0)  # touches the bottom edge: size is a lower bound
    assert describe.est_height_cm(cut, 150) < 140     # would look too short for a person...
    assert identify(cut, (150, 0)) == "person"         # ...but it is cut off, so keep the label
    tall = Box(PERSON, 0.4, 0.0, 0.6, 1.0)
    assert identify(tall, (400, 0)) == "obstacle"      # cut off and still 3 m tall: wrong


def test_no_range_or_off_beam_keeps_camera_label():
    b = box_for(PERSON, 40, 300)
    assert identify(b, None) == "person"
    off_beam = box_for(PERSON, 40, 300, x1=0.0, x2=0.3)
    assert identify(off_beam, (300, 0)) == "person"


def test_unknown_label_and_no_box_are_obstacle():
    assert identify(box_for(UNKNOWN, 100, 200), (200, 0)) == "obstacle"
    assert identify(None, (80, 0)) == "obstacle"


def test_phrases():
    assert phrase(0, "clear", "obstacle", None) == "path clear"
    assert phrase(1, "ahead", "chair", None) == "chair ahead"
    assert phrase(2, "left", "person", (120, 0)) == "person 1.2 meters, go left"
    assert phrase(3, "ahead", "obstacle", (80, 0)) == "Stop. obstacle 80 centimeters"


@pytest.mark.parametrize("line", ["box", "box 0", "box 0 0.1 0.1 0.2", "box x 0.1 0.1 0.2 0.2",
                                  "box 0 0.5 0.1 0.2 0.2", "box 0 0.1 0.1 1.2 0.2", "box none 1", "bax 0 0.1 0.1 0.2 0.2"])
def test_bad_box_lines_rejected(line):
    with pytest.raises((AssertionError, ValueError)):
        io_main.parse_box(line)


def test_parse_box():
    assert io_main.parse_box("box none") is None
    assert io_main.parse_box("box 56 0.1 0.2 0.5 0.9") == Box(56, 0.1, 0.2, 0.5, 0.9)


def make_fusion():
    gpio, clock, said = FakeGpio(), [0.0], []
    actuator = Actuator(gpio=gpio, sleep=lambda s: None, threaded=False)
    return io_main.Fusion(actuator, now=lambda: clock[0], say=said.append), said, clock


def test_fusion_speaks_label_and_distance():
    f, said, _ = make_fusion()
    f.on_line("1 left")
    f.on_line("box 0 0.40 0.05 0.60 0.77")   # 0.72 of the frame: a 170 cm person at 3 m
    f.on_line("range 300.0 0.0")
    assert said[-1] == "person 3.0 meters, go left"


def test_fusion_calls_a_too_small_person_an_obstacle():
    f, said, _ = make_fusion()
    f.on_line("1 left")
    f.on_line("box 0 0.40 0.30 0.60 0.50")   # 0.2 of the frame at 2 m is about 31 cm
    f.on_line("range 200.0 0.0")
    assert said[-1] == "obstacle 2.0 meters, go left"


def test_fusion_does_not_repeat_for_a_changing_distance():
    f, said, _ = make_fusion()
    f.on_line("1 left")
    f.on_line("box 0 0.40 0.05 0.60 0.77")
    f.on_line("range 300.0 0.0")
    n = len(said)
    f.on_line("range 290.0 0.0")
    f.on_line("range 280.0 0.0")
    assert len(said) == n


def test_fusion_stale_box_is_dropped():
    f, said, clock = make_fusion()
    f.on_line("1 left")
    f.on_line("box 0 0.40 0.30 0.60 0.50")
    clock[0] = io_main.RANGE_STALE_S + 0.1
    f.refresh()
    assert said[-2:] == ["person ahead, go left", "obstacle ahead, go left"]
