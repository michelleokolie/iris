# Tasks (pick one stream each)

Create a worktree per stream from the repo root:

```powershell
git worktree add ..\iris-bringup -b bringup-qnx
git worktree add ..\iris-hw -b hw-actuators
git worktree add ..\iris-vision -b vision-alert
git worktree add ..\iris-submit -b mount-submission
```

## A. QNX lead (`bringup-qnx`) - THE BLOCKER
- [x] Boot QNX on the loaner Pi 5 (hostname `iris`, hotspot Wi-Fi, SSH + VNC work)
- [ ] Ask the QNX table: does onnxruntime count as the AI module; broken python3-onnxruntime; can the CPU run above 1500 MHz
- [x] C++ builds on the board with clang++ (see vision/README.md)
- [x] USB webcam enumerates and shows a feed (C920, blue USB 3.0 port, sensor unit 5, `camera_mux -n 1 -u 5`)
- [x] Run `vision/grab_frame` on the Pi (YUYV 640x480)
- [x] onnxruntime runs on the Pi (C++ only; DEIMv2-Femto ~120 ms/frame)
- [ ] Tell C when frames + onnxruntime work; tell B which GPIO/I2C access works

## B. Hardware (`hw-actuators`)
- [ ] Servo wired (separate 5V, shared ground), moves on command
- [ ] 4 LEDs wired and switchable
- [ ] Grove Base Hat or ADC for rotary; accelerometer on I2C; IR sensor
- [ ] Each part works alone before QNX integration; photograph wiring
- [ ] Power bank powers Pi + servo
- [ ] `io` (Python): listen on /tmp/iris.sock, parse Alert lines per docs/interfaces.md, drive servo + LEDs

## C. Software (`vision-alert`)
`vision` is C++ on QNX (camera API is C only, Python onnxruntime is broken); see docs/interfaces.md and vision/README.md.
- [x] capture: frame loop from sensor unit 5 (`vision/capture.cpp`)
- [x] `decide` in C++ (port of PR #3)
- [x] `detect` in C++: DEIMv2-Femto via onnxruntime, ~8 fps full loop on the Pi
- [x] Alert lines over /tmp/iris.sock drive io + real LEDs on the board
- [x] Debounce Alerts (vision/debounce.*), on the board with 1/3/2; tuning via VISION_DEBOUNCE ongoing
- [x] "ahead" = sides within 0.05 (decide.cpp, interfaces.md)
- [x] Ultrasonic fused with the camera in io (hw/fuse.py, PR #12); vision also sends a `box` line per frame for label/size checks (`box-fusion`)
- [x] Camera level 3 = in-path box taller than 0.8 of the frame (no y2 test); verify on the board with a person 3-4 m away (expect level 2)
- [ ] `speak` (Python, in `io`): phrases for Alert and fall; audio route (phone / dongle / Bluetooth)

## D. Build + submission (`mount-submission`)
- [ ] Cardboard/zip-tie chest mount first
- [ ] 3D print: chest plate and servo tap arm (each under about 2h); book a printer slot
- [ ] Demo walk script: walk at chair, warning, step aside, clear; rehearse twice
- [ ] Devpost: all teammates, story, demo video, PCBWay "next version" slide, Sun Life impact slide

## Stretch (anyone, after MVP)
Left/right cues, fall detection (accelerometer, walking-only), Gemini scene description on IR trigger, rotary sensitivity, stereo/downward camera.
