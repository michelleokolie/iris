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
- [ ] Ask the QNX table: does onnxruntime count as the AI module, is it on QNX for Pi 5, and how do we build C++ for the Pi (on-board clang vs SDP cross-compile)
- [x] USB webcam enumerates and shows a feed (C920, blue USB 3.0 port, sensor unit 5, `camera_mux -n 1 -u 5`)
- [ ] Run `vision/grab_frame` on the Pi; report width/height/format
- [ ] onnxruntime runs one image on the Pi; note fps
- [ ] Tell C when frames + onnxruntime work; tell B which GPIO/I2C access works

## B. Hardware (`hw-actuators`)
- [ ] Servo wired (separate 5V, shared ground), moves on command
- [ ] 4 LEDs wired and switchable
- [ ] Grove Base Hat or ADC for rotary; accelerometer on I2C; IR sensor
- [ ] Each part works alone before QNX integration; photograph wiring
- [ ] Power bank powers Pi + servo
- [ ] `io` (Python): listen on /tmp/iris.sock, parse Alert lines per docs/interfaces.md, drive servo + LEDs

## C. Software (`vision-alert`)
`vision` is C++ on QNX (camera API is C only); see docs/interfaces.md.
- [ ] capture: one frame from sensor unit 5 (`vision/grab_frame.cpp` draft), then a frame loop producing `Frame`
- [ ] `decide` in C++ per docs/interfaces.md, tested on laptop with recorded frames
- [ ] `detect` in C++ with an ONNX detector via onnxruntime C/C++ API (laptop first, then Pi; blocked on A's onnxruntime answer)
- [ ] Send Alert lines to /tmp/iris.sock (connect to `io`'s socket, send on change)
- [ ] `speak` (Python, in `io`): phrases for Alert and fall; audio route (phone / dongle / Bluetooth)

## D. Build + submission (`mount-submission`)
- [ ] Cardboard/zip-tie chest mount first
- [ ] 3D print: chest plate and servo tap arm (each under about 2h); book a printer slot
- [ ] Demo walk script: walk at chair, warning, step aside, clear; rehearse twice
- [ ] Devpost: all teammates, story, demo video, PCBWay "next version" slide, Sun Life impact slide

## Stretch (anyone, after MVP)
Left/right cues, fall detection (accelerometer, walking-only), Gemini scene description on IR trigger, rotary sensitivity, stereo/downward camera.
