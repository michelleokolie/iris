import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hw"))

import actuate
from actuate import Actuator
from fake_gpio import FakeGpio


def make():
    gpio, sleeps = FakeGpio(), []
    return Actuator(gpio=gpio, sleep=sleeps.append, threaded=False), gpio, sleeps


def test_level0():
    a, g, _ = make()
    a.alert(0, "clear")
    assert g.state[actuate.LED_GREEN] and not g.state[actuate.LED_RED]
    assert a._level == 0


def test_level1():
    a, g, _ = make()
    a.alert(1, "left")
    assert not g.state[actuate.LED_GREEN] and not g.state[actuate.LED_RED]


def test_level2_3_red():
    a, g, _ = make()
    for level in (2, 3):
        a.alert(level, "right")
        assert g.state[actuate.LED_RED] and not g.state[actuate.LED_GREEN]


def test_describing():
    a, g, _ = make()
    a.describing(True)
    assert g.state[actuate.LED_BLUE_1] and g.state[actuate.LED_BLUE_2]
    a.describing(False)
    assert not g.state[actuate.LED_BLUE_1] and not g.state[actuate.LED_BLUE_2]


def test_servo_pulse_widths():
    a, g, sleeps = make()
    a._tap(3)
    highs = [s for s in sleeps[:-1:2]]
    assert {round(h * 1e6) for h in highs} == {actuate.TAP_US, actuate.REST_US}
    assert all(1000 <= h * 1e6 <= 1800 for h in highs)
    assert g.state[actuate.SERVO] is False


def test_off_switches_every_output_off():
    a, g, _ = make()
    a.alert(3, "ahead")
    a.describing(True)
    a.off()
    assert all(g.state[pin] is False for pin in actuate.OUTPUTS)


def test_off_stops_servo_thread():
    g = FakeGpio()
    a = Actuator(gpio=g, sleep=lambda s: time.sleep(s / 20), threaded=True)
    a.alert(3, "ahead")
    time.sleep(0.05)
    a.off()
    assert not a._thread.is_alive()
    assert all(g.state[pin] is False for pin in actuate.OUTPUTS)


def test_tap_rate_increases_with_level():
    cycles = []
    for level in (1, 2, 3):
        a, _, sleeps = make()
        a._tap(level)
        cycles.append(sum(sleeps))
    assert cycles[0] > cycles[1] > cycles[2]
