"""Bench test on the Pi: sudo python3 hw/bench.py led | buzzer | servo | alerts"""
import sys
import time

import actuate

if len(sys.argv) != 2 or sys.argv[1] not in {"led", "buzzer", "servo", "alerts"}:
    raise SystemExit("usage: sudo python3 hw/bench.py led | buzzer | servo | alerts")
mode = sys.argv[1]
a = actuate.Actuator()

if mode == "led":
    for pin in (actuate.LED_BLUE, actuate.LED_RED, actuate.LED_YELLOW, actuate.LED_GREEN):
        print("pin", pin)
        a._gpio.write(pin, True)
        time.sleep(1)
        a._gpio.write(pin, False)
elif mode == "buzzer":
    for _ in range(3):  # three 0.5 s tones at actuate.TONE_HZ
        print("tone", actuate.TONE_HZ, "Hz")
        a._tone.ChangeDutyCycle(actuate.TONE_DUTY)
        time.sleep(0.5)
        a._tone.ChangeDutyCycle(0)
        time.sleep(0.5)
    a.off()
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
    a.off()
