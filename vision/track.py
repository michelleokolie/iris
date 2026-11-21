from dataclasses import dataclass, field
from itertools import count

from vision.types import Box

IOU_MATCH = 0.3
MAX_MISSED = 5
_ids = count(1)


def _iou(a: Box, b: Box) -> float:
    iw = min(a.x2, b.x2) - max(a.x1, b.x1)
    ih = min(a.y2, b.y2) - max(a.y1, b.y1)
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    union = (a.x2 - a.x1) * (a.y2 - a.y1) + (b.x2 - b.x1) * (b.y2 - b.y1) - inter
    return inter / union


@dataclass
class Track:
    track_id: int
    box: Box
    heights: list[float] = field(default_factory=list)
    missed: int = 0

    @property
    def growth(self) -> float:
        """Change in box height over the last frame (positive = approaching)."""
        if len(self.heights) < 2:
            return 0.0
        return self.heights[-1] - self.heights[-2]


class Tracker:
    """Greedy IoU tracker: stable IDs and approach speed from box height change."""

    def __init__(self) -> None:
        self.tracks: list[Track] = []

    def update(self, boxes: list[Box]) -> list[Track]:
        pairs = sorted(
            ((_iou(t.box, b), ti, bi) for ti, t in enumerate(self.tracks) for bi, b in enumerate(boxes)),
            reverse=True,
        )
        matched_tracks: set[int] = set()
        matched_boxes: set[int] = set()
        for score, ti, bi in pairs:
            if score < IOU_MATCH or ti in matched_tracks or bi in matched_boxes:
                continue
            track = self.tracks[ti]
            track.box = boxes[bi]
            track.heights.append(boxes[bi].y2 - boxes[bi].y1)
            track.missed = 0
            matched_tracks.add(ti)
            matched_boxes.add(bi)

        for ti, track in enumerate(self.tracks):
            if ti not in matched_tracks:
                track.missed += 1

        for bi, box in enumerate(boxes):
            if bi not in matched_boxes:
                self.tracks.append(Track(track_id=next(_ids), box=box, heights=[box.y2 - box.y1]))

        self.tracks = [t for t in self.tracks if t.missed <= MAX_MISSED]
        return self.tracks
