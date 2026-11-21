# Interfaces (change here first)

Two processes. Only the socket message crosses between them.

```
vision (C++)                          io (Python)
capture -> detect -> decide  --Alert-->  actuate (servo, LEDs) + speak
```

## vision (C++, inside one process)

```cpp
// capture -> detect
struct Frame { int width, height; std::vector<uint8_t> bgr; };  // HxWx3, BGR, row-major

// detect -> decide
struct Box { float x1, y1, x2, y2; std::string label; float score; };  // normalized 0..1
std::vector<Box> detect(const Frame& frame);

// decide -> socket
struct Alert { int level; std::string direction; };
// level 0=clear, 1=far, 2=near, 3=imminent
// direction "left" | "right" | "ahead" | "clear" (side with free space)
Alert decide(const std::vector<Box>& boxes);
```

Rules for `decide`:
- in path = box overlaps center strip (x in 0.33..0.67)
- close = box height > 0.5 of frame, or y2 > 0.9
- level: 0 if nothing in path; 3 if an in-path box is close and y2 > 0.9; 2 if an in-path box is close; else 1
- direction = side with more free space (box width overlapping x 0..0.5 vs 0.5..1, all boxes); "ahead" when the two sides are within 0.05 of each other (obstacle roughly centred); "clear" when level 0

## Socket (vision -> io)

- UNIX domain stream socket at `/tmp/iris.sock`. `io` creates and listens; `vision` connects.
- One ASCII line per message, `\n`-terminated, single spaces, nothing else:
  - Alert: `<level> <direction>\n`, level `0`-`3`, direction `left|right|ahead|clear`. Example: `2 left\n`.
  - Fall (later): `fall\n`.
- `vision` sends an Alert only when the debounced Alert changes: level up immediately, level down or back to clear after 3 frames in a row (~0.4 s), same level with a new direction after 2 (~0.25 s). Tunable with VISION_DEBOUNCE=up,down,turn.
- `0 clear\n` is the only valid level-0 message; `clear` never goes with level > 0.

## io (Python)

- actuate: Alert -> servo tap rate + LEDs (green clear, red level>=2; blue while describing)
- speak: Alert | fall -> short phrase string -> audio route

Audio route is undecided: USB dongle, Bluetooth, or text to a phone over Wi-Fi (see docs/decisions.md).
