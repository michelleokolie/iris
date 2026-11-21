import argparse

import cv2

from vision.decide import decide
from vision.depth import DepthEstimator, median_depth_in_box
from vision.detect import Detector
from vision.track import Tracker

DEPTH_EVERY = 3


def run(source: str, detector_path: str, depth_path: str) -> None:
    cap = cv2.VideoCapture(int(source) if source.isdigit() else source)
    detector = Detector(detector_path)
    depth = DepthEstimator(depth_path)
    tracker = Tracker()

    frame_index = 0
    depth_map = None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_index % DEPTH_EVERY == 0:
            depth_map = depth.estimate(frame)

        boxes = detector.detect(frame)
        tracks = tracker.update(boxes)
        alert = decide(boxes)

        summary = [
            (t.track_id, round(t.growth, 4), round(median_depth_in_box(depth_map, t.box), 3))
            for t in tracks
        ]
        print(frame_index, alert, summary)
        frame_index += 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IRIS vision loop: detect, track, depth, decide")
    parser.add_argument("source", help="webcam index (e.g. 0) or video path")
    parser.add_argument("--detector", required=True, help="DEIMv2 ONNX model path")
    parser.add_argument("--depth", required=True, help="Depth Anything 3 small ONNX model path")
    args = parser.parse_args()
    run(args.source, args.detector, args.depth)
