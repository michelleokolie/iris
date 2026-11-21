
"""actuate: Alert states -> LEDs, buzzer, and eventually servo.

GPIO is controlled through /dev/gpio/N on QNX.

Each public state function configures the appropriate hardware outputs.
Background threads handle continuously timed operations.
"""

import threading
import time


# --------------------------------------------------
# GPIO PINS (BCM numbering)
# --------------------------------------------------

LED_BLUE = 17
LED_RED = 22
LED_YELLOW = 23
LED_GREEN = 24

BUZZER = 18  # Physical pin 12, connected through transistor

ALERT_LEDS = (LED_GREEN, LED_YELLOW, LED_RED)
OUTPUTS = (LED_BLUE, LED_RED, LED_YELLOW, LED_GREEN, BUZZER)


# --------------------------------------------------
# BUZZER CONFIGURATION
# --------------------------------------------------

BUZZER_FREQ = 1000  # Target tone frequency (Hz)
BUZZER_GAP_S = 0.08

# Alert cycle durations
ALERT_CYCLE_S = {
    1: 1.5,  # Far
    2: 0.8,  # Near
    3: 0.4,  # Imminent
}

# Beep durations for each alert
BUZZER_PATTERNS = {
    0: (),             # Clear: silent
    1: (0.10,),        # Far: one beep
    2: (0.10, 0.10),   # Near: two beeps
    3: (0.15,),        # Imminent: one longer beep
}


# --------------------------------------------------
# GPIO BACKEND
# --------------------------------------------------

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

    def close(self):
        for fd in self._fds.values():
            fd.close()
        self._fds.clear()


# --------------------------------------------------
# ACTUATOR CONTROLLER
# --------------------------------------------------

class Actuator:

    def __init__(self, gpio=None, sleep=time.sleep, threaded=True):
        self._gpio = gpio if gpio is not None else DevGpio()
        self._sleep = sleep

        self._level = 0
        self._stopped = False

        # Current hardware configuration
        self._buzzer_pattern = ()
        self._buzzer_cycle = None
        self._servo_interval = None  # Reserved for servo integration

        # Synchronize state changes between threads
        self._lock = threading.Lock()
        self._state_changed = threading.Event()

        # Initialize GPIO outputs
        for pin in OUTPUTS:
            self._gpio.set_out(pin)
            self._gpio.write(pin, False)

        # Start buzzer worker
        self._buzzer_thread = (
            threading.Thread(
                target=self._buzzer_loop,
                daemon=True
            )
            if threaded else None
        )

        if self._buzzer_thread is not None:
            self._buzzer_thread.start()

    # ----------------------------------------------
    # PUBLIC ALERT STATE FUNCTIONS
    # ----------------------------------------------

    def clear(self):
        """Clear: green LED, no buzzer, no servo tapping."""
        self._set_state(
            level=0,
            led=LED_GREEN,
            buzzer_pattern=(),
            buzzer_cycle=None,
            servo_interval=None
        )

    def far(self):
        """Far: no alert LED, slow buzzer and servo tapping."""
        self._set_state(
            level=1,
            led=None,
            buzzer_pattern=BUZZER_PATTERNS[1],
            buzzer_cycle=ALERT_CYCLE_S[1],
            servo_interval=1.5
        )

    def near(self):
        """Near: yellow LED, double beeps and medium servo tapping."""
        self._set_state(
            level=2,
            led=LED_YELLOW,
            buzzer_pattern=BUZZER_PATTERNS[2],
            buzzer_cycle=ALERT_CYCLE_S[2],
            servo_interval=0.8
        )

    def imminent(self):
        """Imminent: red LED, rapid buzzer and servo tapping."""
        self._set_state(
            level=3,
            led=LED_RED,
            buzzer_pattern=BUZZER_PATTERNS[3],
            buzzer_cycle=ALERT_CYCLE_S[3],
            servo_interval=0.4
        )

    def alert(self, level, direction):
        """Compatibility interface for existing team code."""

        if level == 0:
            self.clear()
        elif level == 1:
            self.far()
        elif level == 2:
            self.near()
        elif level == 3:
            self.imminent()
        else:
            raise ValueError(f"Invalid alert level: {level}")

    def describing(self, on):
        """Control the separate blue describing LED."""
        self._gpio.write(LED_BLUE, bool(on))

    def off(self):
        """Stop all workers and turn off all outputs."""

        with self._lock:
            self._stopped = True
            self._state_changed.set()

        if self._buzzer_thread is not None:
            self._buzzer_thread.join()

        for pin in OUTPUTS:
            self._gpio.write(pin, False)

        # Only close GPIO if backend supports it
        if hasattr(self._gpio, "close"):
            self._gpio.close()

    # ----------------------------------------------
    # STATE CONFIGURATION HELPER
    # ----------------------------------------------

    def _set_state(
        self,
        level,
        led,
        buzzer_pattern,
        buzzer_cycle,
        servo_interval
    ):
        """Configure hardware for the selected alert state."""

        with self._lock:

            if self._stopped:
                return

            # Don't restart patterns if state hasn't changed
            if self._level == level:
                return

            self._level = level

            # Update buzzer configuration
            self._buzzer_pattern = buzzer_pattern
            self._buzzer_cycle = buzzer_cycle

            # Store servo configuration for future use
            self._servo_interval = servo_interval

            # Update LEDs immediately
            self._set_led(led)

            # Notify the buzzer worker
            self._state_changed.set()

    # ----------------------------------------------
    # LED HELPER
    # ----------------------------------------------

    def _set_led(self, pin):
        """Turn off all alert LEDs, then turn on the selected one."""

        for led in ALERT_LEDS:
            self._gpio.write(led, False)

        if pin is not None:
            self._gpio.write(pin, True)

    # ----------------------------------------------
    # BUZZER HELPERS
    # ----------------------------------------------

    def _buzz(self, duration, level):
        """Generate a square wave for the passive buzzer."""

        half_period = 1.0 / (2 * BUZZER_FREQ)
        end_time = time.monotonic() + duration

        try:
            while time.monotonic() < end_time:

                if self._stopped or self._level != level:
                    break

                self._gpio.write(BUZZER, True)
                self._sleep(half_period)

                self._gpio.write(BUZZER, False)
                self._sleep(half_period)

        finally:
            self._gpio.write(BUZZER, False)

    def _wait(self, duration):
        """Wait for a state change or timeout."""

        changed = self._state_changed.wait(
            timeout=max(0.0, duration)
        )

        if changed:
            self._state_changed.clear()

        return changed

    def _buzzer_loop(self):
        """Continuously perform the configured buzzer pattern."""

        while not self._stopped:

            with self._lock:
                level = self._level
                pattern = self._buzzer_pattern
                cycle = self._buzzer_cycle

            # Clear state: buzzer silent
            if not pattern:
                self._gpio.write(BUZZER, False)
                self._wait(0.1)
                continue

            cycle_start = time.monotonic()

            for index, duration in enumerate(pattern):

                if self._stopped or self._level != level:
                    break

                self._buzz(duration, level)

                if self._stopped or self._level != level:
                    break

                # Gap between consecutive beeps
                if index < len(pattern) - 1:
                    if self._wait(BUZZER_GAP_S):
                        break

            # Wait until the next cycle
            while (
                not self._stopped
                and self._level == level
            ):
                elapsed = time.monotonic() - cycle_start
                remaining = cycle - elapsed

                if remaining <= 0:
                    break

                if self._wait(remaining):
                    break

        self._gpio.write(BUZZER, False)
