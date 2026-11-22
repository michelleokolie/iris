"""Fuse the camera Alert with the ultrasonic range into the Alert that io actuates.

Pure code; thresholds are starting guesses to be tuned on the board, live with
IRIS_RANGE=near,mid,far,ttc_s,ttc_min_closing,confirm (default 60,120,150,1.5,120,3).
camera = (level, direction) from vision; range level = RangeLevel.level, or None (no echo / stale).
"""
import os


def _read_range_settings():
    values = [60.0, 120.0, 150.0, 1.5, 120.0, 3.0]
    if "IRIS_RANGE" in os.environ:
        given = [float(v) for v in os.environ["IRIS_RANGE"].split(",")]
        values[:len(given)] = given
    return values


NEAR_CM, MID_CM, FAR_CM, TTC_S, TTC_MIN_CLOSING, _CONFIRM = _read_range_settings()
# NEAR_CM: closer than this = imminent. MID_CM: near. FAR_CM: far (was 250: indoors a wall or table is almost
# always within 2.5 m). TTC_S: time-to-contact under this = imminent, but only when closing faster than
# TTC_MIN_CLOSING cm/s (was 70: a stationary object's closing speed reads +-60 and noise spikes past 70 faked
# "imminent"; a brisk walk toward the wearer is ~140). CONFIRM: readings in a row before the level may rise.
CONFIRM = int(_CONFIRM)
HYSTERESIS = 1.15   # stay in a level until the distance is 15% past its limit (a reading wanders +-6 cm)


def range_level(cm, closing, prev=0):
    """Level for one range reading; prev = the level in force (for hysteresis)."""
    def within(limit, level):
        return cm < limit * (HYSTERESIS if prev >= level else 1.0)

    if within(NEAR_CM, 3) or (closing > TTC_MIN_CLOSING and cm / closing < TTC_S):
        return 3
    if within(MID_CM, 2):
        return 2
    if within(FAR_CM, 1):
        return 1
    return 0


class RangeLevel:
    """The ultrasonic's level over successive readings. Falling is immediate (hysteresis already keeps it from
    flickering); rising needs CONFIRM readings in a row above the current level, and rises only to the lowest
    of them, so one stray echo or closing-speed spike never reaches the LEDs (~60 ms per reading: 3 = ~0.18 s)."""

    def __init__(self):
        self.level = 0
        self._streak = 0       # readings in a row above self.level
        self._streak_min = 0   # lowest level among them

    def update(self, cm, closing):
        raw = range_level(cm, closing, self.level)
        if raw <= self.level:
            self.level = raw
            self._streak = 0
            return self.level
        self._streak_min = raw if self._streak == 0 else min(self._streak_min, raw)
        self._streak += 1
        if self._streak >= CONFIRM:
            self.level = self._streak_min
            self._streak = 0
        return self.level


def fuse(camera, range_lvl):
    """Either sensor can raise the level, neither can lower the other's (the sonar beam is narrower than the
    camera's in-path strip, so a person off-centre is seen by the camera only). The camera gives the direction.

    range_lvl = RangeLevel.level, or None when there is no current range (camera alone)."""
    cam_level, direction = camera
    if range_lvl is None:
        return camera
    level = max(range_lvl, cam_level)
    if level == 0:
        return 0, "clear"
    if cam_level == 0:
        direction = "ahead"  # only the ultrasonic sees it, so there is no free side to point to
    return level, direction
