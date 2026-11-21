from typing import NamedTuple

import numpy as np

Frame = np.ndarray  # HxWx3 uint8, BGR


class Box(NamedTuple):
    x1: float
    y1: float
    x2: float
    y2: float
    label: str
    score: float


class Alert(NamedTuple):
    level: int  # 0=clear, 1=far, 2=near, 3=imminent
    direction: str  # "left" | "right" | "ahead" | "clear"
