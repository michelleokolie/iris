# Decisions

- 2026-11-21: Detector = small ONNX model via onnxruntime (listed at oss.qnx.com). Confirm with QNX table it counts as the open-source AI module.
- 2026-11-21: One camera for MVP; stereo / downward camera are stretch.
- 2026-11-21: Audio to earbuds is the ideal output; servo + LEDs are the MVP output. Route TBD (phone over Wi-Fi is the default unless QNX Bluetooth works quickly).
- 2026-11-21: No fallback project; no Entire; no GoDaddy domain.
- 2026-11-21: Board hostname `iris`; Wi-Fi via phone/laptop hotspot in boot/wpa_supplicant.conf (venue Wi-Fi doesn't work). SSH `qnxuser@iris.local`; Windows needs `-m hmac-sha2-256`.
- 2026-11-21: Webcam = Logitech C920 in a blue USB 3.0 port; sensor service uses /etc/config/sensor/sensor_rpi5.conf; camera is SENSOR_UNIT 5; live feed verified with `camera_mux -n 1 -u 5`.
- 2026-11-21: QNX camera access isn't supported from Python, so vision (capture/detect/decide) is one C++ process and io (actuate/speak) is Python; they talk over a UNIX socket at /tmp/iris.sock, one line per Alert ("2 left\n").
