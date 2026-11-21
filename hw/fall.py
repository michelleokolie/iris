"""fall: tilt-based fall detection from accelerometer samples (x, y, z in g).

A fall is a jolt (total acceleration far from its resting value, or near zero in free fall), then the device
tilted well away from its resting orientation, then lying still. Impact size is not used: the MMA7660 only
reads +-1.5 g, and a stumble rarely reaches free fall. Constants are starting guesses, checked against one
recording on the board (resting readings step by up to 0.16 g between samples).
"""
import math

MIN_G = 0.2            # total acceleration under this is free fall, which counts as a jolt
JOLT_G = 0.35          # total acceleration this far from its resting value counts as a jolt
JOLT_WINDOW_S = 3.0    # the tilt must start within this long after a jolt
TILT_DEG = 55          # angle from the resting orientation that counts as fallen
RECOVER_DEG = 30       # back within this angle of the resting orientation: got up, not a fall
STILL_G = 0.2          # sample-to-sample change under this counts as still
STILL_S = 2.0          # lying still this long confirms the fall
REF_ALPHA = 0.02       # how fast the resting orientation follows slow drift while upright and calm
COOLDOWN_S = 5.0       # no second report right after one
CALIB_S = 1.0          # still this long at startup to learn the resting orientation


def _norm(v):
    return math.sqrt(sum(a * a for a in v))


def _angle_deg(a, b):
    cos = sum(x * y for x, y in zip(a, b)) / (_norm(a) * _norm(b))
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


class FallDetector:
    def __init__(self):
        self._ref = None          # resting gravity vector; set after CALIB_S of stillness
        self._calib = []          # the still samples collected so far
        self._calib_t = None      # when that stillness began
        self._prev = None
        self._jolt_t = None
        self._still_since = None  # set once tilted after a jolt: when the current stillness began
        self._cooldown_until = 0.0

    def update(self, t, xyz):
        """Feed one sample at time t (seconds). Returns True once per fall."""
        if self._ref is None:  # the device may be in someone's hand at startup: wait for a calm second
            if self._prev is None or _norm([a - b for a, b in zip(xyz, self._prev)]) > STILL_G:
                self._calib, self._calib_t = [xyz], t
            else:
                self._calib.append(xyz)
            self._prev = xyz
            if t - self._calib_t >= CALIB_S:
                self._ref = tuple(sum(c) / len(c) for c in zip(*self._calib))
            return False
        mag = _norm(xyz)
        if mag < MIN_G:  # free fall: no direction to measure
            self._jolt_t = t
            self._prev = xyz
            return False
        if abs(mag - _norm(self._ref)) > JOLT_G:
            self._jolt_t = t
        angle = _angle_deg(xyz, self._ref)
        moving = _norm([a - b for a, b in zip(xyz, self._prev)]) > STILL_G
        self._prev = xyz
        if t < self._cooldown_until:
            return False

        if self._still_since is None:  # no candidate yet
            if angle > TILT_DEG and self._jolt_t is not None and t - self._jolt_t <= JOLT_WINDOW_S:
                self._still_since = t  # tilted right after a jolt: now wait for it to lie still
            elif angle < RECOVER_DEG and not moving:
                self._ref = tuple(r + REF_ALPHA * (a - r) for r, a in zip(self._ref, xyz))
            return False

        if angle < RECOVER_DEG:  # got back up
            self._still_since = None
            return False
        if moving:
            self._still_since = t
            return False
        if t - self._still_since >= STILL_S:
            self._still_since = None
            self._cooldown_until = t + COOLDOWN_S
            return True
        return False
