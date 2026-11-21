from src.speak import Speaker, phrase


def test_phrases():
    assert phrase("fall").startswith("Fall")
    assert phrase((3, "left")) == "Stop! Step left"
    assert phrase((0, "clear")) == "Path clear"


def test_dedupes():
    out = []
    s = Speaker(out.append)
    for e in [(2, "left"), (2, "left"), (0, "clear"), (2, "left")]:
        s.speak(e)
    assert out == ["Obstacle close, move left", "Path clear", "Obstacle close, move left"]
