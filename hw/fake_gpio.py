"""Recording GPIO backend for laptop tests and demos."""


class FakeGpio:
    def __init__(self):
        self.writes = []   # (pin, on) in order
        self.state = {}
        self.outs = []

    def set_out(self, pin):
        self.outs.append(pin)

    def write(self, pin, on):
        self.writes.append((pin, on))
        self.state[pin] = on
