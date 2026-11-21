"""accel: Grove MMA7660FC accelerometer -> (x, y, z) in g, via the hw/accel C helper.

Build on the board: gcc -o accel accel.c. The helper prints raw 6-bit counts, one line per sample.
UNVERIFIED on hardware: DCMD_I2C_SENDRECV usage and chip presence on /dev/i2c1 (see docs/decisions.md).
"""
import subprocess

COUNTS_PER_G = 21.33   # MMA7660FC: 6-bit signed, +-1.5 g -> 32 counts per 1.5 g


def to_g(raw):
    """Raw register byte (bit6 = invalid, bits5..0 = signed 6-bit) -> g."""
    if raw & 0x40:
        raise ValueError("invalid sample")
    v = raw & 0x3F
    if v & 0x20:
        v -= 64
    return v / COUNTS_PER_G


def parse_line(line):
    fields = line.split()
    if len(fields) != 3:
        raise ValueError("expected three-axis sample")
    return tuple(to_g(int(f)) for f in fields)


class Accel:
    def __init__(self, helper="./accel", dev="/dev/i2c1", hz=50):
        self._p = subprocess.Popen([helper, dev, str(hz)], stdout=subprocess.PIPE, text=True)

    def read(self):
        """Blocks for the next sample; returns (x, y, z) in g, ready for FallDetector.update."""
        line = self._p.stdout.readline()
        if line == "":
            raise RuntimeError("accel helper exited")
        return parse_line(line)
