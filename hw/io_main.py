"""io process: listens on a UNIX socket and actuates the fused Alert.

Usage: python hw/io_main.py [--fake] [--socket PATH]
Several clients may connect at once (vision, ultrasonic), one thread each. Line formats
(docs/interfaces.md):
  vision:     "<level> <direction>\n"  level 0-3, direction left|right|ahead|clear;
              "0 clear" is the only level-0 message
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

    def __init__(self, actuator, now=time.monotonic, trace=False):
        self._actuator = actuator
        self._now = now
        self._trace = trace
        self._lock = threading.Lock()
        self._camera = (0, "clear")
        self._range = None  # (cm, closing, received_at) or None
        self._last = None

    def on_line(self, line):
        t = self._now()
        if self._trace:
            print(f"{t:.4f} {line}", flush=True)
        with self._lock:
            if line.startswith("range "):
                r = parse_range(line)
                self._range = None if r is None else (*r, t)
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
        fused = fuse(self._camera, None if rng is None else rng[:2])
        if fused != self._last:
            self._last = fused
            self._actuator.alert(*fused)


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
    fusion = Fusion(actuator, trace=bool(os.environ.get("IRIS_TRACE")))
    server = listen(args.socket)
    threading.Thread(target=watchdog_thread, args=(fusion,), daemon=True).start()
    try:
        while True:
            threading.Thread(target=serve_thread, args=(server.accept()[0], fusion), daemon=True).start()
    finally:
        actuator.off()
