"""Fuse the camera Alert with the ultrasonic range into the Alert that io actuates.

Pure functions; thresholds are starting guesses to be tuned on the board.
camera = (level, direction) from vision; rng = (cm, closing_cm_per_s) or None (no echo / stale).
"""

NEAR_CM = 60    # closer than this: imminent
MID_CM = 120    # closer than this: near
FAR_CM = 150    # closer than this: far (was 250: indoors a wall or table is almost always within 2.5 m)
TTC_S = 1.5     # time-to-contact under this: imminent
HYSTERESIS = 1.15   # stay in a level until the distance is 15% past its limit (a reading wanders +-6 cm)
TTC_MIN_CLOSING = 70  # cm/s; closing speed of a stationary object reads +-60 on the board, walking is 100+


def range_level(cm, closing, prev=0):
    """Level for a range reading; prev = the level this function returned last time (for hysteresis)."""
    def within(limit, level):
        return cm < limit * (HYSTERESIS if prev >= level else 1.0)

    if within(NEAR_CM, 3) or (closing > TTC_MIN_CLOSING and cm / closing < TTC_S):
        return 3
    if within(MID_CM, 2):
        return 2
    if within(FAR_CM, 1):
        return 1
    return 0


def fuse(camera, rng, prev=0):
    """Either sensor can raise the level, neither can lower the other's (the sonar beam is narrower than the
    camera's in-path strip, so a person off-centre is seen by the camera only). The camera gives the direction.

    prev = the previous range level, passed through to range_level."""
    cam_level, direction = camera
    if rng is None:
        return camera
    level = max(range_level(*rng, prev), cam_level)
    if level == 0:
        return 0, "clear"
    if cam_level == 0:
        direction = "ahead"  # only the ultrasonic sees it, so there is no free side to point to
    return level, direction
