"""io process: listens on a UNIX socket and actuates the fused Alert.

Usage: python hw/io_main.py [--fake] [--socket PATH]
Several clients may connect at once (vision, ultrasonic), one thread each. Line formats
(docs/interfaces.md):
  vision:     "<level> <direction>\n"  level 0-3, direction left|right|ahead|clear;
              "0 clear" is the only level-0 message
              "box <label> <x1> <y1> <x2> <y2>\n" or "box none\n": the box driving the Alert
  ultrasonic: "range <cm> <closing_cm_per_s>\n" or "range none\n"
IRIS_TRACE=1 prints a monotonic timestamp per received line, for latency measurements.
"""
import argparse
import os
import signal
import socket
import threading
import time

from actuate import Actuator
from describe import Box, identify, phrase
from fake_gpio import FakeGpio
from fuse import fuse

SOCKET_PATH = "/tmp/iris.sock"
DIRECTIONS = ("left", "right", "ahead", "clear")
RANGE_STALE_S = 0.5  # a range older than this is ignored (sensor stopped or died)


def parse_alert(line):
    level_s, direction = line.split(" ")
    level = int(level_s)
    assert level in (0, 1, 2, 3), line
    assert direction in DIRECTIONS, line
    assert (level == 0) == (direction == "clear"), line
    return level, direction


def parse_box(line):
    """Returns a describe.Box, or None for "box none"."""
    tag, *fields = line.split(" ")
    assert tag == "box", line
    if fields == ["none"]:
        return None
    assert len(fields) == 5, line
    box = Box(int(fields[0]), *(float(c) for c in fields[1:]))
    assert 0 <= box.x1 < box.x2 <= 1 and 0 <= box.y1 < box.y2 <= 1, line
    return box


def parse_range(line):
    """Returns (cm, closing_cm_per_s), or None for "range none"."""
    tag, *fields = line.split(" ")
    assert tag == "range", line
    if fields == ["none"]:
        return None
    cm_s, closing_s = fields
    cm, closing = float(cm_s), float(closing_s)
    assert cm > 0, line
    return cm, closing


class Fusion:
    """Shared state for all clients: latest camera Alert and range, fused and actuated."""

    def __init__(self, actuator, now=time.monotonic, trace=False, say=lambda text: None):
        self._actuator = actuator
        self._now = now
        self._trace = trace
        self._say = say
        self._lock = threading.Lock()
        self._camera = (0, "clear")
        self._box = None    # (Box, received_at) or None
        self._range = None  # (cm, closing, received_at) or None
        self._last = None
        self._last_key = None

    def on_line(self, line):
        t = self._now()
        if self._trace:
            print(f"{t:.4f} {line}", flush=True)
        with self._lock:
            if line.startswith("range "):
                r = parse_range(line)
                self._range = None if r is None else (*r, t)
            elif line.startswith("box "):
                b = parse_box(line)
                self._box = None if b is None else (b, t)
            else:
                self._camera = parse_alert(line)
            self._update(t)

    def refresh(self):
        """Re-evaluate with the current time, so a range that stops arriving still expires."""
        with self._lock:
            self._update(self._now())

    def _update(self, t):
        rng = self._range
        if rng is not None and t - rng[2] > RANGE_STALE_S:
            rng = None
        rng = None if rng is None else rng[:2]
        box = self._box
        if box is not None and t - box[1] > RANGE_STALE_S:
            box = None
        box = None if box is None else box[0]

        fused = fuse(self._camera, rng)
        if fused != self._last:
            self._last = fused
            self._actuator.alert(*fused)
        name = identify(box, rng)
        key = (fused, name, rng is not None)
        if key != self._last_key:  # speak on a change of level, direction, name or having a distance, not of its value
            self._last_key = key
            self._say(phrase(*fused, name, rng))


def block_sigint():
    """QNX delivers SIGINT to any thread that doesn't block it, and Python only handles it in the
    main thread (see docs/decisions.md). Every thread except main blocks it."""
    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})


def listen(path):
    if os.path.exists(path):
        os.remove(path)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    server.listen(4)
    return server


def serve_client(conn, fusion):
    """Feed the lines from one connected client to fusion until it disconnects."""
    with conn, conn.makefile("r", newline="\n") as lines:
        for line in lines:
            assert line.endswith("\n"), repr(line)
            fusion.on_line(line[:-1])


def serve_thread(conn, fusion):
    block_sigint()
    serve_client(conn, fusion)


def watchdog_thread(fusion):
    block_sigint()
    while True:
        time.sleep(RANGE_STALE_S / 5)
        fusion.refresh()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fake", action="store_true", help="use the recording fake GPIO backend")
    ap.add_argument("--socket", default=SOCKET_PATH)
    args = ap.parse_args()
    block_sigint()  # the servo thread inherits the mask; main unblocks it below
    actuator = Actuator(FakeGpio() if args.fake else None)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGINT})
    # No audio route yet (docs/decisions.md), so phrases are printed; swap print for the speaker later.
    fusion = Fusion(actuator, trace=bool(os.environ.get("IRIS_TRACE")), say=lambda text: print(text, flush=True))
    server = listen(args.socket)
    threading.Thread(target=watchdog_thread, args=(fusion,), daemon=True).start()
    try:
        while True:
            threading.Thread(target=serve_thread, args=(server.accept()[0], fusion), daemon=True).start()
    finally:
        actuator.off()
