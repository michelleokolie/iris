from vision.decide import decide
from vision.types import Box


def box(x1, y1, x2, y2):
    return Box(x1, y1, x2, y2, "person", 0.9)


def test_no_boxes_is_clear():
    assert decide([]) == (0, "clear")


def test_box_outside_center_strip_is_clear():
    assert decide([box(0.0, 0.2, 0.2, 0.4)]) == (0, "clear")


def test_small_box_in_path_is_far():
    assert decide([box(0.4, 0.3, 0.6, 0.5)]).level == 1


def test_tall_box_in_path_is_near():
    assert decide([box(0.4, 0.1, 0.6, 0.8)]).level == 2


def test_box_reaching_bottom_is_imminent():
    assert decide([box(0.4, 0.5, 0.6, 0.95)]).level == 3


def test_free_space_on_right_gives_right():
    alert = decide([box(0.0, 0.3, 0.45, 0.5), box(0.4, 0.3, 0.6, 0.5)])
    assert alert.direction == "right"


def test_free_space_on_left_gives_left():
    alert = decide([box(0.55, 0.3, 1.0, 0.5), box(0.4, 0.3, 0.6, 0.5)])
    assert alert.direction == "left"
