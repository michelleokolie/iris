"""Bench test on the Pi: python3 hw/bench.py led | servo | alerts"""
import sys
import time

import actuate

if len(sys.argv) != 2 or sys.argv[1] not in {"led", "servo", "alerts"}:
    raise SystemExit("usage: python3 hw/bench.py led | servo | alerts")
mode = sys.argv[1]
a = actuate.Actuator()

if mode == "led":
    for pin in (actuate.LED_BLUE_1, actuate.LED_BLUE_2, actuate.LED_RED, actuate.LED_GREEN):
        print("pin", pin)
        a._gpio.write(pin, True)
        time.sleep(1)
        a._gpio.write(pin, False)
elif mode == "servo":
    for _ in range(3):
        for us in (actuate.TAP_US, actuate.REST_US):
            for _ in range(50):
                a._pulse(us)
elif mode == "alerts":
    for level, direction in ((0, "clear"), (1, "left"), (2, "right"), (3, "ahead"), (0, "clear")):
        print("alert", level, direction)
        a.alert(level, direction)
        time.sleep(4)
    a.describing(True)
    time.sleep(2)
    a.describing(False)
