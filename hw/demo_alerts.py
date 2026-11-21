"""Demo: python hw/demo_alerts.py [--fake]"""
import sys
import time

import actuate

ALERTS = [(0, "clear"), (1, "left"), (2, "right"), (3, "ahead"), (0, "clear")]

if "--fake" in sys.argv:
    from fake_gpio import FakeGpio
    gpio, pause = FakeGpio(), 0.2
else:
    gpio, pause = None, 4

a = actuate.Actuator(gpio=gpio)
for alert in ALERTS:
    print("alert", alert)
    a.alert(*alert)
    time.sleep(pause)
a.describing(True)
time.sleep(pause)
a.describing(False)
