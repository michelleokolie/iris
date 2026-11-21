import os
import socket
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "hw"))

import actuate
import io_main
from actuate import Actuator
from fake_gpio import FakeGpio


def run(payload, conn_pair):
    """Feed payload to serve_client over a connected socket pair; return the fake GPIO."""
    gpio = FakeGpio()
    actuator = Actuator(gpio=gpio, sleep=lambda s: None, threaded=False)
    server_end, client_end = conn_pair
    client_end.sendall(payload)
    client_end.close()
    io_main.serve_client(server_end, io_main.Fusion(actuator))
    return gpio


@pytest.fixture(params=["socketpair", "unix"])
def pair_factory(request):
    if request.param == "socketpair":
        return socket.socketpair
    if not hasattr(socket, "AF_UNIX"):
        pytest.skip("no AF_UNIX on this platform")

    def unix_pair():
        path = os.path.join(tempfile.mkdtemp(), "iris.sock")
        server = io_main.listen(path)
        c = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        c.connect(path)
        return server.accept()[0], c
    return unix_pair


def test_alert_lines_drive_leds(pair_factory):
    g = run(b"0 clear\n", pair_factory())
    assert g.state[actuate.LED_GREEN] and not g.state[actuate.LED_RED]
    g = run(b"1 right\n", pair_factory())
    assert not g.state[actuate.LED_GREEN] and not g.state[actuate.LED_RED]
    g = run(b"0 clear\n2 left\n", pair_factory())
    assert not g.state[actuate.LED_GREEN] and g.state[actuate.LED_RED]
    g = run(b"2 left\n3 ahead\n1 left\n3 ahead\n", pair_factory())
    assert g.state[actuate.LED_RED]


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="no AF_UNIX")
def test_stale_socket_file_is_removed():
    path = os.path.join(tempfile.mkdtemp(), "iris.sock")
    open(path, "w").close()
    io_main.listen(path).close()


@pytest.mark.parametrize("line", ["fall", "4 left", "2 clear", "0 left", "2  left", "2 up", "x left", "2"])
def test_bad_lines_rejected(line):
    with pytest.raises((AssertionError, ValueError)):
        io_main.parse_alert(line)
