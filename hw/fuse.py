"""Fuse the camera Alert with the ultrasonic range into the Alert that io actuates.

Pure functions; thresholds are starting guesses to be tuned on the board.
camera = (level, direction) from vision; rng = (cm, closing_cm_per_s) or None (no echo / stale).
"""

NEAR_CM = 60    # closer than this: imminent
MID_CM = 120    # closer than this: near
FAR_CM = 250    # closer than this: far
TTC_S = 1.5     # time-to-contact under this: imminent


def range_level(cm, closing):
    if cm < NEAR_CM or (closing > 0 and cm / closing < TTC_S):
        return 3
    if cm < MID_CM:
        return 2
    if cm < FAR_CM:
        return 1
    return 0


def fuse(camera, rng):
    """The ultrasonic sets near/imminent; the camera can only add "far" and the direction."""
    cam_level, direction = camera
    if rng is None:
        return camera
    level = max(range_level(*rng), min(cam_level, 1))
    if level == 0:
        return 0, "clear"
    if cam_level == 0:
        direction = "ahead"  # only the ultrasonic sees it, so there is no free side to point to
    return level, direction
