"""Bench test on the Pi: sudo python3 hw/bench.py led | servo [rest_us tap_us] | blink gpio | sweep | alerts

sweep: finds which pin a jumper is on. It drives each free GPIO in turn, one blink for the first, two for the
second and so on; an LED (with a resistor to ground) on the jumper blinks only during its own pin's group.

servo: three taps between two pulse widths in microseconds. The default, 1400 and 1600, is a gentle swing
(about 36 degrees on a typical servo) for a first test; io's own taps use actuate.REST_US and actuate.TAP_US.
Widths must be between 500 and 2500. Try wider swings once the first run looks right.
blink: GPIO number 2..27 on for 1 s, off for 1 s, ten times: an LED (with a resistor) from that pin to ground
shows whether the pin, the jumper and the ground are right.
"""
import sys
import time

import actuate

USAGE = "usage: sudo python3 hw/bench.py led | servo [rest_us tap_us] | blink gpio | sweep | alerts"
ARG_COUNTS = {"led": (0,), "alerts": (0,), "servo": (0, 2), "blink": (1,), "sweep": (0,)}
# Free GPIOs only (not the I2C, ultrasonic, IR or LED pins), in the order the sweep tries them.
SWEEP_PINS = (4, 5, 6, 9, 12, 13, 17, 19, 20, 21, 22, 26)
mode = sys.argv[1] if len(sys.argv) > 1 else None
args = sys.argv[2:]
if mode not in ARG_COUNTS or len(args) not in ARG_COUNTS[mode]:
    raise SystemExit(USAGE)
if mode == "servo":
    rest_us, tap_us = (int(args[0]), int(args[1])) if args else (1400, 1600)
    assert 500 <= rest_us <= 2500 and 500 <= tap_us <= 2500 and rest_us != tap_us, "widths must be 500..2500 and different"
if mode == "blink":
    pin = int(args[0])
    assert 2 <= pin <= 27, "gpio must be 2..27"

if mode == "blink":
    gpio = actuate.DevGpio()
    gpio.set_out(pin)
    print(f"GPIO {pin}: on 1 s, off 1 s, ten times")
    for _ in range(10):
        gpio.write(pin, True)
        time.sleep(1)
        gpio.write(pin, False)
        time.sleep(1)
    raise SystemExit(0)

if mode == "sweep":
    gpio = actuate.DevGpio()
    for pin in SWEEP_PINS:
        gpio.set_out(pin)
        gpio.write(pin, False)
    for i, pin in enumerate(SWEEP_PINS, 1):
        print(f"{i:2d} blinks = GPIO {pin}", flush=True)
        for _ in range(i):
            gpio.write(pin, True)
            time.sleep(0.2)
            gpio.write(pin, False)
            time.sleep(0.3)
        time.sleep(1.5)
    raise SystemExit(0)

a = actuate.Actuator()
if mode == "led":
    for pin in (actuate.LED_BLUE, actuate.LED_RED, actuate.LED_YELLOW, actuate.LED_GREEN):
        print("pin", pin)
        a._gpio.write(pin, True)
        time.sleep(1)
        a._gpio.write(pin, False)
elif mode == "servo":
    print(f"rest {rest_us} us, tap {tap_us} us: settling at rest for 1 s")
    for _ in range(50):
        a._pulse(rest_us)
    for i in range(3):
        print(f"tap {i + 1}")
        for us in (tap_us, rest_us):
            for _ in range(25):  # 0.5 s at each width
                a._pulse(us)
    a.off()
elif mode == "alerts":
    for level, direction in ((0, "clear"), (1, "left"), (2, "right"), (3, "ahead"), (0, "clear")):
        print("alert", level, direction)
        a.alert(level, direction)
        time.sleep(4)
    a.off()
