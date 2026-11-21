# Interfaces (change here first)

```python
# capture -> detect
Frame = numpy.ndarray            # HxWx3 uint8, BGR

# detect -> decide
Box = (x1: float, y1: float, x2: float, y2: float, label: str, score: float)  # normalized 0..1
detect(frame: Frame) -> list[Box]

# decide -> actuate / speak
Alert = (level: int, direction: str)   # level 0=clear, 1=far, 2=near, 3=imminent
                                       # direction: "left" | "right" | "ahead" | "clear" (side with free space)
decide(boxes: list[Box]) -> Alert

# Rules
# in path  = box overlaps center strip (x in 0.33..0.67)
# close    = box height > 0.5 of frame, or y2 > 0.9
# direction = side with more free space; "clear" when level 0

# actuate: Alert -> servo tap rate + LEDs (green clear, red level>=2; blue while describing)
# speak:   Alert | FallEvent -> short phrase string -> sink(text)   (src/speak.py)
#          phrase(event) -> str;  Speaker(sink).speak(event) skips repeats;  udp_sink(host, port) = phone route
FallEvent = str                        # "fall"
```

Audio route is undecided: USB dongle, Bluetooth, or text to a phone over Wi-Fi (see docs/decisions.md).
