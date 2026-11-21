# Decisions

- 2026-11-21: Detector = small ONNX model via onnxruntime (listed at oss.qnx.com). Confirm with QNX table it counts as the open-source AI module.
- 2026-11-21: One camera for MVP; stereo / downward camera are stretch.
- 2026-11-21: Audio to earbuds is the ideal output; servo + LEDs are the MVP output. Route TBD (phone over Wi-Fi is the default unless QNX Bluetooth works quickly).
- 2026-11-21: No fallback project; no Entire; no GoDaddy domain.
- 2026-11-21: Pi 5 CPU budget: DEIMv2-Femto detector every frame (Apache-2.0), IoU tracker every frame, Depth Anything 3 small every 2-3 frames; skip RF-DETR, YOLO26 (AGPL), metric DA3 large, NCNN until fps is measured on QNX.
- 2026-11-21: Tracker is a greedy IoU tracker (no ByteTrack yet); swap to ByteTrack if IDs flicker on the Pi.
- 2026-11-21: decide(): level 3 = in path and close and y2 > 0.9; direction ties return "ahead".
- 2026-11-21: Depth and track growth are not passed to decide(); changing interfaces.md needs team agreement first.
