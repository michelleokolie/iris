"""ir_trigger: hand-wave trigger from the IR reflective sensor (GPIO27, see docs/decisions.md).

`read` is a callable returning True while the sensor sees a reflection.
"""
import time


class HandWave:
    def __init__(self, read, now=time.monotonic, cooldown_s=2.0):
        self._read = read
        self._now = now
        self._cooldown_s = cooldown_s
        self._prev = False
        self._last = None

    def poll(self):
        """True once per wave: on the rising edge, at most once per cooldown."""
        cur = self._read()
        rising = cur and not self._prev
        self._prev = cur
        if not rising:
            return False
        t = self._now()
        if self._last is not None and t - self._last < self._cooldown_s:
            return False
        self._last = t
        return True
