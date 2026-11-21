"""io process: listens on a UNIX socket for Alert lines from vision and actuates them.

Usage: python hw/io_main.py [--fake] [--socket PATH]
Line format (docs/interfaces.md): "<level> <direction>\n", level 0-3,
direction left|right|ahead|clear; "0 clear" is the only level-0 message.
"""
import argparse
import os
import signal
import socket

from actuate import Actuator
from fake_gpio import FakeGpio

SOCKET_PATH = "/tmp/iris.sock"
DIRECTIONS = ("left", "right", "ahead", "clear")


def parse_alert(line):
    level_s, direction = line.split(" ")
    level = int(level_s)
    assert level in (0, 1, 2, 3), line
    assert direction in DIRECTIONS, line
    assert (level == 0) == (direction == "clear"), line
    return level, direction


def listen(path):
    if os.path.exists(path):
        os.remove(path)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    server.listen(1)
    return server


def serve_client(conn, actuator):
    """Actuate the Alerts from one connected vision client until it disconnects."""
    with conn, conn.makefile("r", newline="\n") as lines:
        for line in lines:
            assert line.endswith("\n"), repr(line)
            actuator.alert(*parse_alert(line[:-1]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fake", action="store_true", help="use the recording fake GPIO backend")
    ap.add_argument("--socket", default=SOCKET_PATH)
    args = ap.parse_args()
    # QNX delivers SIGINT to any thread that doesn't block it; Python only handles it in the
    # main thread, which sits in accept(). Block it while the servo thread starts (threads
    # inherit the mask) so Ctrl-C always reaches the main thread.
    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT})
    actuator = Actuator(FakeGpio() if args.fake else None)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGINT})
    server = listen(args.socket)
    try:
        while True:  # one client at a time; vision may reconnect after a restart
            serve_client(server.accept()[0], actuator)
    finally:
        actuator.off()
