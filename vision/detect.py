import cv2
import numpy as np
import onnxruntime as ort

from vision.types import Box, Frame

SCORE_THRESHOLD = 0.4


class Detector:
    """DEIMv2 ONNX detector (CPU). Input/output names follow the DEIM export script; verify against the model file."""

    def __init__(self, model_path: str) -> None:
        self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.input_h, self.input_w = self.session.get_inputs()[0].shape[2:4]

    def detect(self, frame: Frame) -> list[Box]:
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(cv2.resize(frame, (self.input_w, self.input_h)), cv2.COLOR_BGR2RGB)
        images = rgb.transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        sizes = np.array([[h, w]], dtype=np.int64)
        labels, boxes, scores = self.session.run(None, {"images": images, "orig_target_sizes": sizes})

        out: list[Box] = []
        for label, (x1, y1, x2, y2), score in zip(labels[0], boxes[0], scores[0]):
            if score < SCORE_THRESHOLD:
                continue
            out.append(Box(x1 / w, y1 / h, x2 / w, y2 / h, str(int(label)), float(score)))
        return out
