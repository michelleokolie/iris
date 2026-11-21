# Decisions

- 2026-11-21: Detector = small ONNX model via onnxruntime (listed at oss.qnx.com). Confirm with QNX table it counts as the open-source AI module.
- 2026-11-21: One camera for MVP; stereo / downward camera are stretch.
- 2026-11-21: Audio to earbuds is the ideal output; servo + LEDs are the MVP output. Route TBD (phone over Wi-Fi is the default unless QNX Bluetooth works quickly).
- 2026-11-21: No fallback project; no Entire; no GoDaddy domain.
- 2026-11-21: Whole pipeline stays Python on the Pi (no C++ vision process, no /tmp/iris.sock split); `vision` and `actuate`/`speak` run in one Python process. Supersedes the closed PR #2 proposal.
- 2026-11-21: On the board (QNX 8.0, Python 3.14): `import cv2` works (4.12.0, numpy 2.4.1). `cv2.VideoCapture` on the webcam is not yet verified. Python `onnxruntime` imports but fails: missing `onnxruntime.capi.onnxruntime_pybind11_state` (native module not installed).
