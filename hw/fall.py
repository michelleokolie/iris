"""fall: FallEvent detection from accelerometer samples (x, y, z in g).

Free fall (|a| < FREEFALL_G) followed within WINDOW_S by an impact (|a| > IMPACT_G, sensor range is +-1.5 g).
"""
import math

FREEFALL_G = 0.4
IMPACT_G = 1.3   # MMA7660FC clips at 1.5 g
WINDOW_S = 1.0


class FallDetector:
    def __init__(self):
        self._freefall_t = None

    def update(self, t, xyz):
        """Feed one sample at time t (seconds). Returns True on a fall."""
        g = math.sqrt(sum(a * a for a in xyz))
        if g < FREEFALL_G:
            self._freefall_t = t
            return False
        if g > IMPACT_G and self._freefall_t is not None and t - self._freefall_t <= WINDOW_S:
            self._freefall_t = None
            return True
        return False
