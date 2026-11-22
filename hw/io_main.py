"""io process: listens on a UNIX socket and actuates the fused Alert.

Usage: sudo python3 hw/io_main.py [--socket PATH]
Several clients may connect at once (vision, ultrasonic), one thread each. A thread reads the
phone page that speaks io's sentences (hw/speak.py,
http://<pi address>:8080/). Line formats (docs/interfaces.md):
  vision:     "<level> <direction>\n"  level 0-3, direction left|right|ahead|clear;
              "0 clear" is the only level-0 message
              "box <label> <x1> <y1> <x2> <y2>\n" or "box none\n": the box driving the Alert
  ultrasonic: "range <cm> <closing_cm_per_s>\n" or "range none\n"
IRIS_TRACE=1 prints a monotonic timestamp per received line, for latency measurements.
"""
import argparse
import os
import queue
import signal
import socket
import threading
import time
import traceback

from actuate import Actuator
from describe import Box, identify, phrase, position
import fuse as fuse_settings
from fuse import RangeLevel, fuse
from speak import PhoneSpeaker

SOCKET_PATH = "/tmp/iris.sock"
DIRECTIONS = ("left", "right", "ahead", "clear")
BOX_STALE_S = 0.5    # a box older than this is ignored (vision sends one every frame, ~0.12 s)
RANGE_HOLD_S = 1.0   # the last good range is kept this long, through "range none" gaps (41% no-echo on the board)
VISION_STALE_S = 1.5  # no vision line (box or Alert) for this long = camera lost (vision sends a box every ~0.12 s)
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
        self._range_levels = RangeLevel()  # ultrasonic level: hysteresis down, CONFIRM readings to go up
        self._vision_t = None  # when the last vision line (box or Alert) arrived; None until the first
        self._camera_lost = False
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
                    self._range_levels.update(*r)  # once per reading, so CONFIRM counts readings
            elif line.startswith("box "):
                b = parse_box(line)
                self._box = None if b is None else (b, t)
                self._vision_t = t
            else:
                self._camera = parse_alert(line)
                self._vision_t = t
            self._update(t)

    def refresh(self):
        """Re-evaluate with the current time, so a range that stops arriving still expires."""
        with self._lock:
            self._update(self._now())

    def _update(self, t):
        lost = self._vision_t is not None and t - self._vision_t > VISION_STALE_S
        if lost:  # forget the camera so a stale Alert can't come back when vision reconnects
            self._camera = (0, "clear")
            self._box = None
        if lost != self._camera_lost:  # said directly: not rate limited, not urgent
            self._camera_lost = lost
            self._say("Camera lost" if lost else "Camera back")
        rng = self._range
        if rng is not None and t - rng[2] > RANGE_HOLD_S:
            rng = None
        rng = None if rng is None else rng[:2]
        box = self._box
        if box is not None and t - box[1] > BOX_STALE_S:
            box = None
        box = None if box is None else box[0]

        if rng is None:  # no current range: start over, so a stale level can't come back with the next reading
            self._range_levels = RangeLevel()
        fused = fuse(self._camera, None if rng is None else self._range_levels.level)
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


class RangeForward:
    """SAMPLE (display only): copy each ultrasonic range line to the vision connection(s), for vision's
    preview bar. A connection counts as vision once it has sent an Alert or box line.

    Must never hold anything up. Each vision connection has its own small queue and writer thread: send() only
    does put_nowait (a full queue drops the copy) and returns, so the ultrasonic thread and vision's reader
    thread never wait on vision reading. Only that connection's writer can block (vision busy, e.g. loading the
    model), and it holds no lock. (The first version sent under a shared lock and deadlocked on the board.)"""

    QUEUE_LINES = 8

    def __init__(self):
        self._queues = {}  # conn -> queue of encoded lines
        self._lock = threading.Lock()

    def add(self, conn):
        with self._lock:
            if conn in self._queues:
                return
            q = queue.Queue(maxsize=self.QUEUE_LINES)
            self._queues[conn] = q
        threading.Thread(target=self._writer, args=(conn, q), daemon=True).start()

    def remove(self, conn):
        with self._lock:
            q = self._queues.pop(conn, None)
        if q is not None:
            try:
                q.put_nowait(None)  # wake the writer so it exits; if the queue is full, closing conn ends it
            except queue.Full:
                pass

    def send(self, line):
        data = (line + "\n").encode()
        with self._lock:
            queues = list(self._queues.values())
        for q in queues:
            try:
                q.put_nowait(data)
            except queue.Full:
                pass  # vision isn't keeping up: drop this copy (display only)

    @staticmethod
    def _writer(conn, q):
        while (data := q.get()) is not None:
            try:
                conn.sendall(data)
            except OSError:
                return  # vision disconnected (its reader thread removes it): normal at a socket boundary


def serve_client(conn, fusion, forward):
    """Feed the lines from one connected client to fusion until it disconnects."""
    with conn, conn.makefile("r", newline="\n") as lines:
        try:
            for line in lines:
                assert line.endswith("\n"), repr(line)
                line = line[:-1]
                if line.startswith("range "):
                    forward.send(line)
                else:
                    forward.add(conn)  # Alert/box lines: this is vision, it gets the range copies
                fusion.on_line(line)
        finally:
            forward.remove(conn)


def run_thread(body, *args):
    """Entry point of every io thread: block SIGINT, run body, and if it raises take io down.

    A dead client thread would leave io running camera-only with no warning (this happened on the
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--socket", default=SOCKET_PATH)
    args = ap.parse_args()
    signal.signal(signal.SIGINT, signal.default_int_handler)  # run.sh starts io from a shell that leaves SIGINT ignored
    block_sigint()  # the servo thread inherits the mask; main unblocks it below
    actuator = Actuator(thread_runner=run_thread)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGINT})
    speaker = PhoneSpeaker()  # binds the port here so a port already in use stops io at startup

    def say(text):  # every sentence goes to the console and to the phone page
        print(text, flush=True)
        speaker.say(text)

    fusion = Fusion(actuator, trace=bool(os.environ.get("IRIS_TRACE")), say=say)
    print(f"range levels: 3 under {fuse_settings.NEAR_CM:g} cm or closing > {fuse_settings.TTC_MIN_CLOSING:g} cm/s "
          f"with < {fuse_settings.TTC_S:g} s to contact; 2 under {fuse_settings.MID_CM:g}; 1 under {fuse_settings.FAR_CM:g}; "
          f"rise after {fuse_settings.CONFIRM} readings", flush=True)
    server = listen(args.socket)
    forward = RangeForward()  # SAMPLE: range lines copied to vision for its preview bar
    threading.Thread(target=run_thread, args=(speaker.serve,), daemon=True).start()
    threading.Thread(target=run_thread, args=(watchdog_loop, fusion), daemon=True).start()
    try:
        while True:
            threading.Thread(target=run_thread, args=(serve_client, server.accept()[0], fusion, forward), daemon=True).start()
    finally:
        actuator.off()
