from vision.types import Alert, Box

STRIP_LEFT = 0.33
STRIP_RIGHT = 0.67


def _in_path(box: Box) -> bool:
    return box.x2 > STRIP_LEFT and box.x1 < STRIP_RIGHT


def _close(box: Box) -> bool:
    return (box.y2 - box.y1) > 0.5 or box.y2 > 0.9


def _occupancy(boxes: list[Box], lo: float, hi: float) -> float:
    total = 0.0
    for box in boxes:
        overlap = min(box.x2, hi) - max(box.x1, lo)
        if overlap > 0:
            total += overlap
    return total


def decide(boxes: list[Box]) -> Alert:
    blocking = [b for b in boxes if _in_path(b)]
    if not blocking:
        return Alert(level=0, direction="clear")

    if any(b.y2 > 0.9 and _close(b) for b in blocking):
        level = 3
    elif any(_close(b) for b in blocking):
        level = 2
    else:
        level = 1

    left = _occupancy(boxes, 0.0, 0.5)
    right = _occupancy(boxes, 0.5, 1.0)
    if left < right:
        direction = "left"
    elif right < left:
        direction = "right"
    else:
        direction = "ahead"
    return Alert(level=level, direction=direction)
