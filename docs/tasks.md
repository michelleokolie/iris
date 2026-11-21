# Tasks (pick one stream each)

Create a worktree per stream from the repo root:

```powershell
git worktree add ..\iris-bringup -b bringup-qnx
git worktree add ..\iris-hw -b hw-actuators
git worktree add ..\iris-vision -b vision-alert
git worktree add ..\iris-submit -b mount-submission
```

## A. QNX lead (`bringup-qnx`) - THE BLOCKER
- [ ] Boot QNX on the loaner Pi 5
- [ ] Ask the QNX table: does onnxruntime count as the AI module, and which camera path is supported
- [ ] USB webcam enumerates; capture a frame
- [ ] onnxruntime runs one image on the Pi; note fps
- [ ] Tell C when frames + onnxruntime work; tell B which GPIO/I2C access works

## B. Hardware (`hw-actuators`)
- [ ] Servo wired (separate 5V, shared ground), moves on command
- [ ] 4 LEDs wired and switchable
- [ ] Grove Base Hat or ADC for rotary; accelerometer on I2C; IR sensor
- [ ] Each part works alone before QNX integration; photograph wiring
- [ ] Power bank powers Pi + servo

## C. Software (`vision-alert`)
- [ ] `decide` per docs/interfaces.md, tested on laptop with webcam/test video
- [ ] `detect` with an ONNX detector on laptop, then port to Pi
- [ ] `speak`: phrases for Alert and fall; audio route (phone / dongle / Bluetooth)
- [ ] Integrate `actuate` once B's pins are known

## D. Build + submission (`mount-submission`)
- [ ] Cardboard/zip-tie chest mount first
- [ ] 3D print: chest plate and servo tap arm (each under about 2h); book a printer slot
- [ ] Demo walk script: walk at chair, warning, step aside, clear; rehearse twice
- [ ] Devpost: all teammates, story, demo video, PCBWay "next version" slide, Sun Life impact slide

## Stretch (anyone, after MVP)
Left/right cues, fall detection (accelerometer, walking-only), Gemini scene description on IR trigger, rotary sensitivity, stereo/downward camera.
