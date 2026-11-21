"""ir_read: read() for HandWave from the IR reflective sensor on GPIO27 via QNX rpi_gpio (/dev/gpio/27).

UNVERIFIED on QNX: that writing "in" selects input and that a read of /dev/gpio/N returns "0"/"1" text
(parse() crashes on anything else, so the first bench run shows the real format). UNVERIFIED: sensor polarity.
"""
PIN = 27


def parse(data):
    return {b"0": False, b"1": True}[data.strip()]


class IrReader:
    def __init__(self, pin=PIN, active_high=True):
        self._path = f"/dev/gpio/{pin}"
        self._active_high = active_high
        with open(self._path, "wb", buffering=0) as f:
            f.write(b"in")

    def read(self):
        """True while the sensor sees a reflection."""
        with open(self._path, "rb", buffering=0) as f:
            return parse(f.read()) == self._active_high
