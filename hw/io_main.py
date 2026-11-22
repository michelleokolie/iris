"""io process: listens on a UNIX socket and actuates the fused Alert.

Usage: sudo python3 hw/io_main.py [--socket PATH]   (needs hw/accel built: gcc -o hw/accel hw/accel.c)
Several clients may connect at once (vision, ultrasonic), one thread each. A thread reads the
accelerometer and reports falls; another serves the phone page that speaks io's sentences (hw/speak.py,
http://<pi address>:8080/). Line formats (docs/interfaces.md):
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
import traceback

from accel import Accel
from actuate import Actuator
from describe import FALL, Box, identify, phrase, position
from fall import FallDetector
from fuse import fuse, range_level
from speak import PhoneSpeaker

SOCKET_PATH = "/tmp/iris.sock"
ACCEL_HELPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accel")
ACCEL_HZ = 25
DIRECTIONS = ("left", "right", "ahead", "clear")
BOX_STALE_S = 0.5    # a box older than this is ignored (vision sends one every frame, ~0.12 s)
RANGE_HOLD_S = 1.0   # the last good range is kept this long, through "range none" gaps (41% no-echo on the board)
SAY_MIN_GAP_S = 1.0  # at most one sentence per this, unless the level goes up


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
        self._range_level = 0  # last range level, for hysteresis
        self._said_level = 0
        self._said_t = None

    def on_line(self, line):
        t = self._now()
        if self._trace:
            print(f"{t:.4f} {line}", flush=True)
        with self._lock:
            if line.startswith("range "):
                r = parse_range(line)
                if r is not None:  # "range none" keeps the last good range until RANGE_HOLD_S passes
                    self._range = (*r, t)
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

    def on_fall(self):
        with self._lock:
            if self._trace:
                print(f"{self._now():.4f} fall", flush=True)
            self._say(FALL)

    def _update(self, t):
        rng = self._range
        if rng is not None and t - rng[2] > RANGE_HOLD_S:
            rng = None
        rng = None if rng is None else rng[:2]
        box = self._box
        if box is not None and t - box[1] > BOX_STALE_S:
            box = None
        box = None if box is None else box[0]

        fused = fuse(self._camera, rng, self._range_level)
        self._range_level = 0 if rng is None else range_level(*rng, self._range_level)
        if fused != self._last:
            self._last = fused
            self._actuator.alert(*fused)
        name = identify(box, rng)
        where = position(box)
        key = (0,) if fused[0] == 0 else (fused[0], where, name, rng is not None)  # level 0 always says "path clear"
        if key == self._last_key:  # speak on a change of level, position, name or having a distance, not of its value
            return
        escalates = fused[0] > self._said_level
        if escalates or self._said_t is None or t - self._said_t >= SAY_MIN_GAP_S:
            self._last_key = key
            self._said_level = fused[0]
            self._said_t = t
            self._say(phrase(fused[0], where, name, rng))  # otherwise a later refresh() says it once the gap has passed


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


def run_thread(body, *args):
    """Entry point of every io thread: block SIGINT, run body, and if it raises take io down.

    A dead client or accelerometer thread would leave io running camera-only with no warning (this happened on the
    bench when an assert killed the ultrasonic client), so the failure goes to the main thread as a SIGINT: it raises
    KeyboardInterrupt there, the finally block switches the outputs off, and io exits with the traceback."""
    block_sigint()
    try:
        body(*args)
    except Exception:
        traceback.print_exc()
        os.kill(os.getpid(), signal.SIGINT)


def watchdog_loop(fusion):
    while True:
        time.sleep(BOX_STALE_S / 5)
        fusion.refresh()


def fall_loop(accel, fusion):
    detector = FallDetector()
    while True:
        if detector.update(time.monotonic(), accel.read()):
            fusion.on_fall()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--socket", default=SOCKET_PATH)
    args = ap.parse_args()
    block_sigint()  # the servo thread inherits the mask; main unblocks it below
    actuator = Actuator(thread_runner=run_thread)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGINT})
    accel = Accel(helper=ACCEL_HELPER, hz=ACCEL_HZ)  # created here so a missing helper stops io at startup
    speaker = PhoneSpeaker()  # binds the port here so a port already in use stops io at startup

    def say(text):  # every sentence goes to the console and to the phone page
        print(text, flush=True)
        speaker.say(text)

    fusion = Fusion(actuator, trace=bool(os.environ.get("IRIS_TRACE")), say=say)
    server = listen(args.socket)
    threading.Thread(target=run_thread, args=(speaker.serve,), daemon=True).start()
    threading.Thread(target=run_thread, args=(watchdog_loop, fusion), daemon=True).start()
    threading.Thread(target=run_thread, args=(fall_loop, accel, fusion), daemon=True).start()
    try:
        while True:
            threading.Thread(target=run_thread, args=(serve_client, server.accept()[0], fusion), daemon=True).start()
    finally:
        actuator.off()
