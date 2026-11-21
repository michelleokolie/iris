# Interfaces (change here first)

Three processes. Only the socket messages cross between them; both clients connect to `io`.

```
vision (C++)                                    io (Python)
capture -> detect -> decide -> debounce --Alert, Box--> fuse -> actuate (servo, LEDs) + speak
ultrasonic (C++, hw/ultrasonic.cpp) ----Range-->   fuse
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

## Socket (clients -> io)

- UNIX domain stream socket at `/tmp/iris.sock`. `io` creates and listens, one thread per client; `vision` and the C++ `ultrasonic` reader (`hw/ultrasonic.cpp`) both connect.
- One ASCII line per message, `\n`-terminated, single spaces, nothing else:
  - Alert (vision): `<level> <direction>\n`, level `0`-`3`, direction `left|right|ahead|clear`. Example: `2 left\n`.
  - Box (vision): `box <label> <x1> <y1> <x2> <y2>\n`, label = COCO class index, coordinates normalized 0..1 (`box 0 0.40 0.05 0.60 0.77\n`), or `box none\n` when nothing is in path. It is the in-path box that drives the Alert (highest level, then tallest, `primary_box` in `vision/decide.cpp`). Sent every frame, independent of the Alert debounce, so `io` has fresh geometry.
  - Range (ultrasonic): `range <cm> <closing_cm_per_s>\n` (closing > 0 = getting closer), or `range none\n` when no echo came back. The reader sends nothing while a jump of more than 50 cm from the last accepted reading awaits confirmation (the next reading within 15 cm); the closing speed is the least-squares slope over the last 7 medians, clamped to +-300, and 0 until 3 medians exist (after `range none` or an accepted jump). Example: `range 84.5 31.0\n`.
- `vision` sends an Alert only when the debounced Alert changes: level up immediately, level down or back to clear after 3 frames in a row (~0.4 s), same level with a new direction after 2 (~0.25 s). Tunable with VISION_DEBOUNCE=up,down,turn. `ultrasonic` sends one Range per measurement (~every 60 ms).
- `0 clear\n` is the only valid level-0 message; `clear` never goes with level > 0.

## io (Python)

- fuse (`hw/fuse.py`): camera Alert + Range -> the Alert to actuate. The level is the higher of the ultrasonic's (distance and time-to-contact) and the camera's; the camera gives the direction; an obstacle only the ultrasonic sees is direction `ahead`. "range none" keeps the last good range for 1 s (the sensor loses its echo on soft or angled surfaces), and a range older than that falls back to the camera Alert alone. A level is kept until the distance is 15% past its limit (hysteresis), and the closing speed only counts toward time-to-contact above 70 cm/s (a stationary object reads +-60). Thresholds are starting guesses, tuned on the board.
- describe (`hw/describe.py`): box + range -> a name and a phrase. Real height ~ box height * distance / F_NORM; if that disagrees with the label's expected height (small table: person, bicycle, car, bench, dog, chair, couch, table) the name becomes "obstacle". A box cut off by the frame edge is only rejected when too tall. A box and range are only compared when the box overlaps the beam's image strip. A box older than 0.5 s is ignored. Phrases ("Stop. person 1.2 meters, go left") are said when level, direction, name or having-a-distance changes, not when the distance value changes, at most once per second unless the level goes up (a held-back sentence is said once the second has passed). No audio route yet, so `io_main.py` prints them.
- actuate: fused Alert -> servo tap rate + LEDs (green clear, red level>=2)
- fall (`hw/accel` helper -> `hw/accel.py` -> `hw/fall.py`, a thread inside `io`, no socket): the MMA7660 accelerometer at 25 Hz; a fall is a jolt (total acceleration far from its resting value, or near zero), then a tilt of more than 55 degrees from the resting orientation within 3 s, then lying still (sample changes under 0.2 g) for 2 s; getting back within 30 degrees cancels it. `Fusion.on_fall` says "Fall detected". Thresholds are untested starting guesses.
- speak (`src/speak.py`): Alert | fall -> short phrase string -> `sink(text)`. `phrase(event)`, `Speaker(sink).speak(event)` skips repeats, `udp_sink(host, port)` = phone route. `io_main.py` still prints its describe phrases; pass `Speaker(udp_sink(...)).sink` as `say` to route them.

Audio route is undecided: USB dongle, Bluetooth, or text to a phone over Wi-Fi (see docs/decisions.md).
