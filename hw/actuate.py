"""actuate: Alert -> LEDs, buzzer and servo tap. Pins are GPIO numbers (see docs/decisions.md).

LEDs and the servo are driven by text writes to /dev/gpio/N (QNX rpi_gpio). The servo is on GPIO5, which has
no hardware PWM, so it is software PWM from a thread. The passive buzzer is on GPIO18, a hardware PWM pin: its
tone comes from QNX's rpi_gpio PWM (the GPIO resource manager), not from Python toggling the pin, which can't
hold a kHz square wave on QNX. Python only switches the tone on and off for each beep.

States (level): 0 green, silent / 1 no LED, silent / 2 yellow, two beeps every 0.8 s / 3 red, one long beep
every 0.4 s. The servo taps at every level above 0.
"""
import threading
import time

import rpi_gpio as GPIO

LED_BLUE = 17   # unused by io for now; kept off
LED_RED = 22
LED_YELLOW = 23
LED_GREEN = 24
BUZZER = 18     # passive buzzer through a transistor; hardware PWM pin
SERVO = 5
OUTPUTS = (LED_BLUE, LED_RED, LED_YELLOW, LED_GREEN, SERVO)  # /dev/gpio pins; the buzzer belongs to rpi_gpio PWM

REST_US = 1000
TAP_US = 1800
PERIOD_S = 0.020
DWELL_PULSES = 10           # 0.2 s to let the horn reach each position
REST_SLICE_S = 0.05         # granularity for noticing a level change between taps
TAP_CYCLE_S = {1: 1.5, 2: 0.8, 3: 0.4}  # level -> time per tap

TONE_HZ = 2000              # passive buzzers are loudest around 2-4 kHz
TONE_DUTY = 50              # percent; 0 = silent
BEEP_GAP_S = 0.08
BEEPS = {2: (0.10, 0.10), 3: (0.15,)}   # level -> beep lengths per cycle; levels 0 and 1 are silent
BEEP_CYCLE_S = {2: 0.8, 3: 0.4}


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
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(BUZZER, GPIO.OUT)
        self._tone = GPIO.PWM(BUZZER, TONE_HZ, mode=GPIO.PWM.MODE_MS)
        self._tone.ChangeDutyCycle(0)
        self._level = 0
        self._stopped = False
        self._threads = []
        for loop in (self._servo_loop, self._buzzer_loop):
            if thread_runner is None:
                t = threading.Thread(target=loop, daemon=True)
            else:
                t = threading.Thread(target=thread_runner, args=(loop,), daemon=True)
            t.start()
            self._threads.append(t)

    def off(self):
        """Stop the servo and buzzer threads and switch every output off (GPIO keeps its last state)."""
        self._stopped = True
        for t in self._threads:
            t.join()
        for pin in OUTPUTS:
            self._gpio.write(pin, False)
        self._tone.ChangeDutyCycle(0)
        self._tone.stop()

    def alert(self, level, direction):
        # LEDs are written on every call (not only on a change), so the first "0 clear" lights green.
        self._level = level
        self._gpio.write(LED_GREEN, level == 0)
        self._gpio.write(LED_YELLOW, level == 2)
        self._gpio.write(LED_RED, level == 3)

    def _wait(self, seconds, level):
        """Sleep in slices; False as soon as the level changes or io stops."""
        end = time.monotonic() + seconds
        while (left := end - time.monotonic()) > 0:
            if self._stopped or self._level != level:
                return False
            time.sleep(min(left, REST_SLICE_S))
        return not self._stopped and self._level == level

    def _buzzer_loop(self):
        while not self._stopped:
            level = self._level
            if level not in BEEPS:
                time.sleep(REST_SLICE_S)
                continue
            start = time.monotonic()
            for i, length in enumerate(BEEPS[level]):
                if i and not self._wait(BEEP_GAP_S, level):
                    break
                self._tone.ChangeDutyCycle(TONE_DUTY)
                time.sleep(length)
                self._tone.ChangeDutyCycle(0)
            self._wait(BEEP_CYCLE_S[level] - (time.monotonic() - start), level)
        self._tone.ChangeDutyCycle(0)

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
        self._wait(max(0.0, TAP_CYCLE_S[level] - 2 * DWELL_PULSES * PERIOD_S), level)

    def _servo_loop(self):
        while not self._stopped:
            level = self._level
            if level == 0:
                time.sleep(REST_SLICE_S)
                continue
            self._tap(level)
