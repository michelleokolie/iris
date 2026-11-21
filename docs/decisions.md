# Decisions

- 2026-11-21: Detector = small ONNX model via onnxruntime (listed at oss.qnx.com). Confirm with QNX table it counts as the open-source AI module.
- 2026-11-21: One camera for MVP; stereo / downward camera are stretch.
- 2026-11-21: Audio to earbuds is the ideal output; servo + LEDs are the MVP output. Route TBD (phone over Wi-Fi is the default unless QNX Bluetooth works quickly).
- 2026-11-21: No fallback project; no Entire; no GoDaddy domain.
- 2026-11-21: Board is QNX 8.0 on Pi 5, Python 3.14, gcc on board. GPIO = text writes to /dev/gpio/N (rpi_gpio); no /dev/pwm, so servo is software PWM in hw/actuate.py. Header I2C (GPIO2/3 = SDA1/SCL1) is /dev/i2c1 (group i2c); hw/i2cscan.c probes it.
- 2026-11-21: Proposed pin map (unverified until wired): LED blue GPIO17/22, red GPIO23, green GPIO24, servo signal GPIO18, IR GPIO27, accelerometer on pins 3/5 (3.3V pin 1, GND pin 6). Servo power from the bank, not the Pi 5V pin. Level 1 shows neither green nor red (spec only defines green=clear, red>=2).
- 2026-11-21: Our Grove modules need a Grove-to-Dupont cable to reach the header; accelerometer not yet seen on /dev/i2c1 (suspect wiring).
- 2026-11-21: Verified on the board: 4 LEDs work on GPIO17 (blue, pin 11), GPIO22 (blue, pin 15), GPIO23 (red, pin 16), GPIO24 (green, pin 18); shared ground via pin 9. Resistors 330 ohm (blue) and 220 ohm (red, green). Driven by writing out/on/off to /dev/gpio/N as qnxuser (group gpio).
- 2026-11-21: Verified on the board: Grove 3-axis accelerometer is an MMA7660 at 0x4c on /dev/i2c1 (header pins 3/5, 3.3V pin 1, GND pin 6, via Grove-to-Dupont cable). Must write 0x01 to register 0x07 (MODE) to activate; X/Y/Z are registers 0x00-0x02, 6-bit signed, ~21 counts/g.
