# vision (C++)

capture -> detect (DEIMv2 via onnxruntime) -> decide, sends Alert lines to `/tmp/iris.sock` (see docs/interfaces.md).

Files: `capture.*` (QNX camera API), `detect.*` (DEIMv2), `decide.*` (rules), `debounce.*` (stable Alerts), `preview.*` + `glyphs.h` (optional VNC window, built-in 5x7 font and COCO names), `main.cpp` (loop + socket).
Tools: `grab_frame.cpp` (save one frame), `ort_smoke.cpp` (time any ONNX model).

## Build on the Pi

One-time: `sudo apk add qnx-sf-base-dev qnx-screen-dev onnxruntime-dev`

```sh
clang++ -std=c++17 -O2 main.cpp capture.cpp detect.cpp decide.cpp debounce.cpp preview.cpp -o vision -lcamapi -lonnxruntime -lsocket -lscreen
```

## Run

Stop `camera_mux` first. Model needs both `deimv2_femto.onnx` and `deimv2_femto.onnx.data` in the same folder.

```sh
./vision deimv2_femto.onnx                  # print only
./vision deimv2_femto.onnx /tmp/iris.sock   # also send Alerts to io (io must be listening)
```

Live preview on the Pi's screen (watch over VNC), for tuning and demos; works with or without io:

```sh
sudo VISION_PREVIEW=1 ./vision deimv2_femto.onnx /tmp/iris.sock
```

The window shows the camera frame, every detection (thin grey) labelled with its COCO name and score (`PERSON 87`), the box driving the Alert (thick, in the level's colour), the in-path strip (blue lines at x 0.33 and 0.67), and a bar on top coloured by level (green 0, grey 1, yellow 2, red 3) reading e.g. `LEVEL 2 RIGHT`, with a white marker on the free side.

Start `io` first (`hw/io_main.py`), then `vision`. The ultrasonic reader (`hw/ultrasonic.cpp`) also connects to `io` on `/tmp/iris.sock`; `io` combines it with the camera Alert (`hw/fuse.py`). Besides the debounced Alert, `vision` sends a `box` line every frame (the in-path box that drives the Alert, see docs/interfaces.md) so `io` can check labels and sizes against the ultrasonic distance.
