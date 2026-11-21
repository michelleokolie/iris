"""actuate: Alert -> LEDs + servo tap. Pins are GPIO numbers (see docs/decisions.md).

GPIO is driven by text writes to /dev/gpio/N (QNX rpi_gpio). No hardware PWM
exists, so the servo is software PWM from a thread.
"""
import threading
import time

LED_BLUE_1 = 17
LED_BLUE_2 = 22
LED_RED = 23
LED_GREEN = 24
SERVO = 18

REST_US = 1000
TAP_US = 1800
PERIOD_S = 0.020
DWELL_PULSES = 10           # 0.2 s to let the horn reach each position
TAP_CYCLE_S = {1: 1.5, 2: 0.8, 3: 0.4}  # level -> time per tap

_fds = {}


def _open(pin):
    path = f"/dev/gpio/{pin}"
    with open(path, "wb", buffering=0) as f:
        f.write(b"out")
    _fds[pin] = open(path, "wb", buffering=0)


def _write(pin, on):
    _fds[pin].write(b"on" if on else b"off")


def _pulse(us):
    _write(SERVO, True)
    time.sleep(us / 1e6)
    _write(SERVO, False)
    time.sleep(PERIOD_S - us / 1e6)


class Actuator:
    def __init__(self):
        for pin in (LED_BLUE_1, LED_BLUE_2, LED_RED, LED_GREEN, SERVO):
            _open(pin)
            _write(pin, False)
        self._level = 0
        threading.Thread(target=self._servo_loop, daemon=True).start()

    def alert(self, level, direction):
        self._level = level
        _write(LED_GREEN, level == 0)
        _write(LED_RED, level >= 2)

    def describing(self, on):
        _write(LED_BLUE_1, on)
        _write(LED_BLUE_2, on)

    def _servo_loop(self):
        while True:
            level = self._level
            if level == 0:
                time.sleep(0.05)
                continue
            for us in (TAP_US, REST_US):
                for _ in range(DWELL_PULSES):
                    _pulse(us)
            time.sleep(max(0.0, TAP_CYCLE_S[level] - 2 * DWELL_PULSES * PERIOD_S))
