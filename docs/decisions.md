# Decisions

- 2026-11-21: Detector = small ONNX model via onnxruntime (listed at oss.qnx.com). Confirm with QNX table it counts as the open-source AI module.
- 2026-11-21: One camera for MVP; stereo / downward camera are stretch.
- 2026-11-21: Audio to earbuds is the ideal output; servo + LEDs are the MVP output. Route TBD (phone over Wi-Fi is the default unless QNX Bluetooth works quickly).
- 2026-11-21: No fallback project; no Entire; no GoDaddy domain.
- 2026-11-21: Board is QNX 8.0 on Pi 5, Python 3.14, gcc on board. GPIO = text writes to /dev/gpio/N (rpi_gpio); no /dev/pwm, so servo is software PWM in hw/actuate.py. Header I2C (GPIO2/3 = SDA1/SCL1) is /dev/i2c1 (group i2c); hw/i2cscan.c probes it.
- 2026-11-21: Proposed pin map (unverified until wired): LED blue GPIO17/22, red GPIO23, green GPIO24, servo signal GPIO18, IR GPIO27, accelerometer on pins 3/5 (3.3V pin 1, GND pin 6). Servo power from the bank, not the Pi 5V pin. Level 1 shows neither green nor red (spec only defines green=clear, red>=2).
- 2026-11-21: Our Grove modules need a Grove-to-Dupont cable to reach the header; accelerometer not yet seen on /dev/i2c1 (suspect wiring).
- 2026-11-21: hw/actuate.py takes `Actuator(gpio=...)` (object with set_out(pin), write(pin, on)); default DevGpio writes /dev/gpio/N, hw/fake_gpio.py records writes for tests/demo (`python hw/demo_alerts.py --fake`).
- 2026-11-21: hw/ir_trigger.py (HandWave: rising edge + cooldown) and hw/fall.py (FallDetector: freefall <0.4g then impact >1.3g (MMA7660FC at 0x4C, +-1.5g) within 1s) take injected readers/samples; real GPIO27 read and I2C accelerometer read are not written yet (chip and QNX read path unverified).
- 2026-11-21: Whole pipeline stays Python on the Pi (no C++ vision process, no /tmp/iris.sock split); `vision` and `actuate`/`speak` run in one Python process. Supersedes the closed PR #2 proposal.
- 2026-11-21: On the board (QNX 8.0, Python 3.14): `import cv2` works (4.12.0, numpy 2.4.1). `cv2.VideoCapture` on the webcam is not yet verified. Python `onnxruntime` is installed, but `import onnxruntime` fails: missing `onnxruntime.capi.onnxruntime_pybind11_state` (native module not installed).
- 2026-11-21: hw/io_main.py is the io process: listens on /tmp/iris.sock (`--socket`, `--fake`), one vision client at a time, parses `<level> <direction>` lines (asserts on bad format; `fall` not handled yet) into Actuator.alert; `hw/send_alert.py 2 left` sends one line for bench tests.
