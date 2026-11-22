"""actuate: Alert -> LEDs + servo tap. Pins are GPIO numbers (see docs/decisions.md).

GPIO is driven by text writes to /dev/gpio/N (QNX rpi_gpio). The servo is on GPIO5, which has no hardware
PWM, so it is software PWM from a thread.

States (level): 0 green / 1 no LED / 2 yellow / 3 red. The servo taps at every level above 0, faster as the
level rises. No buzzer: the passive buzzer was dropped (see docs/decisions.md); the phone speaks instead.
"""
import threading
import time

LED_BLUE = 17   # unused by io for now; kept off
LED_RED = 27
LED_YELLOW = 23
LED_GREEN = 24
SERVO = 5
OUTPUTS = (LED_BLUE, LED_RED, LED_YELLOW, LED_GREEN, SERVO)

REST_US = 1000
TAP_US = 1800
PERIOD_S = 0.020
DWELL_PULSES = 10           # 0.2 s to let the horn reach each position
REST_SLICE_S = 0.05         # granularity for noticing a level change between taps
TAP_CYCLE_S = {1: 1.5, 2: 0.8, 3: 0.4}  # level -> time per tap


class DevGpio:
    """Default backend: text writes to /dev/gpio/N."""

    def __init__(self):
        self._fds = {}

    def set_out(self, pin):
        path = f"/dev/gpio/{pin}"
        with open(path, "wb", buffering=0) as f:
            f.write(b"out")
        self._fds[pin] = open(path, "wb", buffering=0)

    def write(self, pin, on):
        self._fds[pin].write(b"on" if on else b"off")


class Actuator:
    def __init__(self, thread_runner=None):
        self._gpio = DevGpio()
        for pin in OUTPUTS:
            self._gpio.set_out(pin)
            self._gpio.write(pin, False)
        self._level = 0
        self._stopped = False
        if thread_runner is None:
            self._thread = threading.Thread(target=self._servo_loop, daemon=True)
        else:
            self._thread = threading.Thread(target=thread_runner, args=(self._servo_loop,), daemon=True)
        self._thread.start()

    def off(self):
        """Stop the servo thread and switch every output pin off (GPIO keeps its last state)."""
        self._stopped = True
        self._thread.join()
        for pin in OUTPUTS:
            self._gpio.write(pin, False)

    def alert(self, level, direction):
        # LEDs are written on every call (not only on a change), so the first "0 clear" lights green.
        self._level = level
        self._gpio.write(LED_GREEN, level == 0)
        self._gpio.write(LED_YELLOW, level == 2)
        self._gpio.write(LED_RED, level == 3)

    def _pulse(self, us):
        self._gpio.write(SERVO, True)
        time.sleep(us / 1e6)
        self._gpio.write(SERVO, False)
        time.sleep(PERIOD_S - us / 1e6)

    def _tap(self, level):
        for us in (TAP_US, REST_US):
            for _ in range(DWELL_PULSES):
                if self._stopped:
                    return
                self._pulse(us)
        # Wait out the rest of the cycle in slices so a level change starts the next tap early.
        rest = max(0.0, TAP_CYCLE_S[level] - 2 * DWELL_PULSES * PERIOD_S)
        for _ in range(round(rest / REST_SLICE_S)):
            if self._stopped or self._level != level:
                return
            time.sleep(REST_SLICE_S)

    def _servo_loop(self):
        while not self._stopped:
            level = self._level
            if level == 0:
                time.sleep(REST_SLICE_S)
                continue
            self._tap(level)
