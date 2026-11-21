import cv2
import numpy as np
import onnxruntime as ort

from vision.types import Box, Frame

MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class DepthEstimator:
    """Depth Anything 3 small ONNX (relative depth). Input/output layout must be verified against the model file."""

    def __init__(self, model_path: str) -> None:
        self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.input_h, self.input_w = self.session.get_inputs()[0].shape[2:4]

    def estimate(self, frame: Frame) -> np.ndarray:
        rgb = cv2.cvtColor(cv2.resize(frame, (self.input_w, self.input_h)), cv2.COLOR_BGR2RGB)
        norm = (rgb.astype(np.float32) / 255.0 - MEAN) / STD
        (depth,) = self.session.run(None, {self.input_name: norm.transpose(2, 0, 1)[None]})
        return np.squeeze(depth)


def median_depth_in_box(depth_map: np.ndarray, box: Box) -> float:
    h, w = depth_map.shape
    x1, x2 = int(box.x1 * w), max(int(box.x2 * w), int(box.x1 * w) + 1)
    y1, y2 = int(box.y1 * h), max(int(box.y2 * h), int(box.y1 * h) + 1)
    return float(np.median(depth_map[y1:y2, x1:x2]))
