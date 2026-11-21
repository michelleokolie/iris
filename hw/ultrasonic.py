#!/usr/bin/env python3
"""HC-SR04 distance + closing speed on QNX (Pi 5).

Port of the team's Arduino sketch (median of 3, closing speed over 7 readings)
onto QNX's rpi_gpio, following qnx/Raspberry-Pi-Hardware-Component-Samples
hc-sr04_ultrasonic_sensor/python/Ultrasonic.py.

Wiring: VCC 5 V, GND shared, TRIG direct to a GPIO, ECHO through the 1k/2k
divider to a GPIO (docs/decisions.md). Pins are BCM numbers.

Run as root (rpi_gpio needs it):  sudo python3 ultrasonic.py TRIG_PIN ECHO_PIN
"""

import statistics
import sys
import time
from collections import deque

import rpi_gpio as GPIO

SPEED_OF_SOUND_CM_PER_S = 34300
ECHO_TIMEOUT_S = 0.025  # ~4.3 m round trip, same as the Arduino pulseIn timeout
SAMPLE_INTERVAL_S = 0.060  # HC-SR04 needs ~60 ms between pings
FILTER_SIZE = 3  # median of the last 3 raw readings
WINDOW_SIZE = 7  # closing speed from oldest vs newest of the last 7 filtered readings


def busy_wait(seconds):
    start = time.perf_counter()
    while time.perf_counter() - start < seconds:
        pass


def read_cm(trig, echo):
    """One raw reading in cm, or None if the echo didn't come back in time."""
    GPIO.output(trig, False)
    busy_wait(2e-6)
    GPIO.output(trig, True)
    busy_wait(10e-6)
    GPIO.output(trig, False)

    start = time.perf_counter()
    while GPIO.input(echo) == 0:
        if time.perf_counter() - start > ECHO_TIMEOUT_S:
            return None
    pulse_start = time.perf_counter()
    while GPIO.input(echo) == 1:
        if time.perf_counter() - pulse_start > ECHO_TIMEOUT_S:
            return None
    pulse_s = time.perf_counter() - pulse_start
    return pulse_s * SPEED_OF_SOUND_CM_PER_S / 2


def main():
    trig, echo = int(sys.argv[1]), int(sys.argv[2])
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(trig, GPIO.OUT)
    GPIO.setup(echo, GPIO.IN, pull_up_down=GPIO.PUD_OFF)
    GPIO.output(trig, False)
    time.sleep(0.5)  # let the sensor settle

    raw = deque(maxlen=FILTER_SIZE)
    history = deque(maxlen=WINDOW_SIZE)  # (time_s, filtered_cm)
    try:
        while True:
            t0 = time.monotonic()
            cm = read_cm(trig, echo)
            if cm is None:
                print("No valid echo")
                raw.clear()
                history.clear()  # don't compute speed across a gap
            else:
                raw.append(cm)
                if len(raw) == FILTER_SIZE:
                    filtered = statistics.median(raw)
                    history.append((time.monotonic(), filtered))
                    (t_old, d_old), (t_new, d_new) = history[0], history[-1]
                    # Positive = getting closer.
                    speed = (d_old - d_new) / (t_new - t_old) if t_new > t_old else 0.0
                    print(f"Distance: {filtered:7.2f} cm | Closing speed: {speed:7.2f} cm/s")
            time.sleep(max(0.0, SAMPLE_INTERVAL_S - (time.monotonic() - t0)))
    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
