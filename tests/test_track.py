from vision.track import MAX_MISSED, Tracker
from vision.types import Box


def box(x1, y1, x2, y2):
    return Box(x1, y1, x2, y2, "person", 0.9)


def test_same_object_keeps_id_across_frames():
    tracker = Tracker()
    first = tracker.update([box(0.4, 0.3, 0.6, 0.5)])[0].track_id
    second = tracker.update([box(0.41, 0.31, 0.61, 0.51)])[0].track_id
    assert first == second


def test_growing_box_reports_positive_approach_speed():
    tracker = Tracker()
    tracker.update([box(0.4, 0.3, 0.6, 0.4)])
    (track,) = tracker.update([box(0.39, 0.25, 0.61, 0.45)])
    assert track.growth > 0


def test_track_dropped_after_too_many_missed_frames():
    tracker = Tracker()
    tracker.update([box(0.4, 0.3, 0.6, 0.5)])
    for _ in range(MAX_MISSED + 1):
        tracker.update([])
    assert tracker.tracks == []
