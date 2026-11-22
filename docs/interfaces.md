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
- very close = box height > 0.8 of frame (height only: camera tilt cuts feet off and makes y2 meaningless for distance)
- level: 0 if nothing in path; 3 if an in-path box is very close; 2 if an in-path box is close; else 1
- direction = side with more free space (box width overlapping x 0..0.5 vs 0.5..1, all boxes); "ahead" when the two sides are within 0.05 of each other (obstacle roughly centred); "clear" when level 0

## Socket (clients -> io)

- UNIX domain stream socket at `/tmp/iris.sock`. `io` creates and listens, one thread per client; `vision` and the C++ `ultrasonic` reader (`hw/ultrasonic.cpp`) both connect.
- One ASCII line per message, `\n`-terminated, single spaces, nothing else:
  - Alert (vision): `<level> <direction>\n`, level `0`-`3`, direction `left|right|ahead|clear`. Example: `2 left\n`.
  - Box (vision): `box <label> <x1> <y1> <x2> <y2>\n`, label = COCO class index, coordinates normalized 0..1 (`box 0 0.40 0.05 0.60 0.77\n`), or `box none\n` when nothing is in path. It is the in-path box that drives the Alert (highest level, then tallest, `primary_box` in `vision/decide.cpp`). Sent every frame, independent of the Alert debounce, so `io` has fresh geometry.
  - Range (ultrasonic): `range <cm> <closing_cm_per_s>\n` (closing > 0 = getting closer), or `range none\n` when no echo came back (an echo shorter than 120 us, under the HC-SR04's 2 cm minimum, counts as no echo). The reader sends nothing while a jump of more than 50 cm from the last accepted reading awaits confirmation (the next reading within 15 cm); the closing speed is the least-squares slope over the last 7 medians, clamped to +-300, and 0 until 3 medians exist (after `range none` or an accepted jump). Example: `range 84.5 31.0\n`.
- `vision` sends an Alert only when the debounced Alert changes: level up immediately, level down or back to clear after 3 frames in a row (~0.4 s), same level with a new direction after 2 (~0.25 s). Tunable with VISION_DEBOUNCE=up,down,turn. `ultrasonic` sends one Range per measurement (~every 60 ms).
- `0 clear\n` is the only valid level-0 message; `clear` never goes with level > 0.

## io (Python)

- fuse (`hw/fuse.py`): camera Alert + Range -> the Alert to actuate. The level is the higher of the ultrasonic's (distance and time-to-contact) and the camera's; the camera gives the direction; an obstacle only the ultrasonic sees is direction `ahead`. "range none" keeps the last good range for 1 s (the sensor loses its echo on soft or angled surfaces), and a range older than that falls back to the camera Alert alone. A level is kept until the distance is 15% past its limit (hysteresis), and the closing speed only counts toward time-to-contact above 70 cm/s (a stationary object reads +-60). Thresholds are starting guesses, tuned on the board.
- describe (`hw/describe.py`): box + range -> a name and a phrase. Real height ~ box height * distance / F_NORM; if that disagrees with the label's expected height (small table: person, bicycle, car, bench, dog, chair, couch, table) the name becomes "obstacle". A box cut off by the frame edge is only rejected when too tall. A box and range are only compared when the box overlaps the beam's image strip. A box older than 0.5 s is ignored. Phrases say where the OBJECT is, from the primary box centre (x < 0.33 "to your left", > 0.67 "to your right", else "in front of you"; no box = "an obstacle in front of you"): "A chair to your left, about two meters away", "Careful! A person in front of you, about one and a half meters away" at level 3 (the opening word is picked at random from Stop!, Watch out!, Careful!, Hold on!; under 20 cm it says "very close" instead of a number) (distance only when a range is known: nearest 10 cm under 1 m, else nearest half metre), "path clear" at level 0, "Fall detected. Are you okay?" for a fall. They are said when level, position, name or having-a-distance changes, not when the distance value changes, at most once per second unless the level goes up (a held-back sentence is said once the second has passed). `io_main.py` prints them and sends them to the phone (speak).
- actuate: fused Alert -> servo tap rate + LEDs (green clear, red level>=2)
- fall (`hw/accel` helper -> `hw/accel.py` -> `hw/fall.py`, a thread inside `io`, no socket): the MMA7660 accelerometer at 25 Hz; a fall is a jolt (total acceleration far from its resting value, or near zero), then a tilt of more than 55 degrees from the resting orientation within 3 s, then lying still (sample changes under 0.2 g) for 2 s; getting back within 30 degrees cancels it. `Fusion.on_fall` says "Fall detected". Thresholds are untested starting guesses.
- failure: every io thread (one per client, the range/box watchdog, the accelerometer reader) runs under `run_thread`; if one raises (for example a malformed line from a client), io prints the traceback, switches the outputs off and exits, instead of carrying on without that sensor. A client that simply disconnects is not a failure.
- speak (`hw/speak.py`, `PhoneSpeaker`, a thread inside `io`): every sentence `Fusion` says (the fused-alert phrases and "Fall detected") is printed and also sent to a phone. `io` serves a small page on port 8080; the phone, on the same Wi-Fi as the Pi, opens `http://<pi address>:8080/`, taps Start once (phones only speak after a tap) and the page speaks each sentence, received over a server-sent-events stream at `/events`. The page shows Connected / Reconnecting and the last sentence in large text, has a Test voice button, and requests a screen wake lock on Start and again when it becomes visible (the API needs a secure context, so over plain http a browser may refuse; the page then says so). The page picks the most natural English voice the phone offers (Siri, Premium, Enhanced) and shows its name. Phones may stop speech when the screen locks. A sentence is never cut off by an ordinary update: it finishes first and only the newest ordinary sentence waits; only warnings ("!") and falls interrupt (not another urgent one still being spoken). The port is bound when `io` starts, so a port already in use stops `io`.

Audio route: phone over Wi-Fi for now. A USB audio dongle or Bluetooth straight from the Pi is still possible; both are untested on QNX (see docs/decisions.md).
