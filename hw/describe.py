"""describe: use the ultrasonic distance to sanity-check the camera's label, and word the result.

Real height ~ box height (fraction of the frame) * distance / F_NORM. If that disagrees with what the
label should measure, the label (or the box-to-beam match) is probably wrong, so say "obstacle".
Every constant here is an untested starting guess: calibrate F_NORM and BEAM_X on the board.
"""
import random
from collections import namedtuple

Box = namedtuple("Box", "label x1 y1 x2 y2")  # label = COCO class index; coordinates normalized 0..1

F_NORM = 1.27           # camera focal length in frame heights: F_NORM = box_h * cm / real_height_cm
BEAM_X = (0.40, 0.60)   # image x-range the ultrasonic beam covers
EDGE = 0.02             # a box within this of a frame edge is cut off, so its size is a lower bound
SLACK = (0.6, 1.5)      # tolerance around a label's expected height range

NAMES = {0: "person", 1: "bicycle", 2: "car", 13: "bench", 16: "dog", 56: "chair", 57: "couch", 60: "table"}
HEIGHT_CM = {0: (140, 200), 1: (80, 120), 2: (130, 200), 13: (40, 110), 16: (20, 80),
             56: (70, 110), 57: (60, 110), 60: (60, 90)}


def in_beam(box):
    return box.x1 < BEAM_X[1] and box.x2 > BEAM_X[0]


def est_height_cm(box, cm):
    return (box.y2 - box.y1) * cm / F_NORM


def plausible(box, cm):
    est = est_height_cm(box, cm)
    lo, hi = HEIGHT_CM[box.label]
    if box.y1 <= EDGE or box.y2 >= 1 - EDGE:
        return est <= hi * SLACK[1]  # cut off: it can only be taller than measured
    return lo * SLACK[0] <= est <= hi * SLACK[1]


def identify(box, rng):
    """The camera's label if the measured distance agrees with it, else "obstacle".

    box: Box or None; rng: (cm, closing_cm_per_s) or None."""
    name = None if box is None else NAMES.get(box.label)
    if name is None:
        return "obstacle"
    if rng is None or not in_beam(box):
        return name  # nothing to check it against
    return name if plausible(box, rng[0]) else "obstacle"


PATH_X = (0.33, 0.67)  # image x-range of the camera's in-path strip (same strip vision decides on)
FALL = "Fall detected. Are you okay?"
WARNINGS = ["Stop!", "Stop!", "Watch out!", "Careful!", "Hold on!"]  # level 3 opens with one, picked at random
VERY_CLOSE_CM = 20  # nearer than this says "very close" instead of a number
WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}


def position(box):
    """Where the object is: "in front of you", "to your left" or "to your right" (no box: in front)."""
    if box is None:
        return "in front of you"
    centre = (box.x1 + box.x2) / 2
    if centre < PATH_X[0]:
        return "to your left"
    if centre > PATH_X[1]:
        return "to your right"
    return "in front of you"


def distance_text(cm):
    """Nearest 10 cm from 20 cm to a metre, else nearest half metre: "40 centimeters", "one and a half meters"."""
    if cm < 100:
        return f"{round(cm / 10) * 10} centimeters"
    halves = round(cm / 50)  # distance in half metres
    whole, half = divmod(halves, 2)
    if half:
        return f"{WORDS[whole]} and a half meters"
    return "one meter" if whole == 1 else f"{WORDS[whole]} meters"


def phrase(level, where, name, rng, pick=random.choice):
    """Short sentence for the wearer, e.g. "Careful! A chair to your left, about two meters away".

    where: position() text; rng: (cm, closing) or None; pick chooses the level-3 warning word."""
    if level == 0:
        return "path clear"
    article = "an" if name[0] in "aeiou" else "a"
    text = f"{article} {name} {where}".capitalize()
    if rng is not None:
        text += ", very close" if rng[0] < VERY_CLOSE_CM else f", about {distance_text(rng[0])} away"
    if level == 3:
        text = f"{pick(WARNINGS)} {text}"
    return text
