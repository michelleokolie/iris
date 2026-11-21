# Decisions

- 2026-11-21: Detector = small ONNX model via onnxruntime (listed at oss.qnx.com). Confirm with QNX table it counts as the open-source AI module.
- 2026-11-21: One camera for MVP; stereo / downward camera are stretch.
- 2026-11-21: Audio to earbuds is the ideal output; servo + LEDs are the MVP output. Route TBD (phone over Wi-Fi is the default unless QNX Bluetooth works quickly).
- 2026-11-21: No fallback project; no Entire; no GoDaddy domain.
- 2026-11-21: Board is QNX 8.0 on Pi 5, Python 3.14, gcc on board. GPIO = text writes to /dev/gpio/N (rpi_gpio); no /dev/pwm, so servo is software PWM in hw/actuate.py. Header I2C (GPIO2/3 = SDA1/SCL1) is /dev/i2c1 (group i2c); hw/i2cscan.c probes it.
- 2026-11-21: Proposed pin map (unverified until wired): LED blue GPIO17/22, red GPIO23, green GPIO24, servo signal GPIO18, IR GPIO27, accelerometer on pins 3/5 (3.3V pin 1, GND pin 6). Servo power from the bank, not the Pi 5V pin. Level 1 shows neither green nor red (spec only defines green=clear, red>=2).
- 2026-11-21: Our Grove modules need a Grove-to-Dupont cable to reach the header; accelerometer not yet seen on /dev/i2c1 (suspect wiring).
- 2026-11-21: hw/actuate.py takes `Actuator(gpio=...)` (object with set_out(pin), write(pin, on)); default DevGpio writes /dev/gpio/N, hw/fake_gpio.py records writes for tests/demo (`python hw/demo_alerts.py --fake`).
