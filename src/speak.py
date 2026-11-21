import socket

PHRASES = {
    (0, "clear"): "Path clear",
    (1, "left"): "Obstacle ahead, bear left",
    (1, "right"): "Obstacle ahead, bear right",
    (1, "ahead"): "Obstacle ahead",
    (2, "left"): "Obstacle close, move left",
    (2, "right"): "Obstacle close, move right",
    (2, "ahead"): "Obstacle close, slow down",
    (3, "left"): "Stop! Step left",
    (3, "right"): "Stop! Step right",
    (3, "ahead"): "Stop!",
}


def phrase(event) -> str:
    if event == "fall":
        return "Fall detected. Are you okay?"
    return PHRASES[event]


def udp_sink(host: str, port: int):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return lambda text: sock.sendto(text.encode(), (host, port))


class Speaker:
    """Calls sink(text) only when the phrase changes (no repeating the same warning every frame)."""

    def __init__(self, sink):
        self.sink = sink
        self.last = None

    def speak(self, event) -> None:
        text = phrase(event)
        if text != self.last:
            self.last = text
            self.sink(text)
