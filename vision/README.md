# vision (C++)

capture -> detect (DEIMv2 via onnxruntime) -> decide, sends Alert lines to `/tmp/iris.sock` (see docs/interfaces.md).

Files: `capture.*` (QNX camera API), `detect.*` (DEIMv2), `decide.*` (rules), `debounce.*` (stable Alerts), `main.cpp` (loop + socket).
Tools: `grab_frame.cpp` (save one frame), `ort_smoke.cpp` (time any ONNX model).

## Build on the Pi

One-time: `sudo apk add qnx-sf-base-dev qnx-screen-dev onnxruntime-dev`

```sh
clang++ -std=c++17 -O2 main.cpp capture.cpp detect.cpp decide.cpp debounce.cpp -o vision -lcamapi -lonnxruntime -lsocket
```

## Run

Stop `camera_mux` first. Model needs both `deimv2_femto.onnx` and `deimv2_femto.onnx.data` in the same folder.

```sh
./vision deimv2_femto.onnx                  # print only
./vision deimv2_femto.onnx /tmp/iris.sock   # also send Alerts to io (io must be listening)
```

Start `io` first (`hw/io_main.py`), then `vision`. The ultrasonic reader (`hw/ultrasonic.cpp`) also connects to `io` on `/tmp/iris.sock`; `io` combines it with the camera Alert (`hw/fuse.py`). Besides the debounced Alert, `vision` sends a `box` line every frame (the in-path box that drives the Alert, see docs/interfaces.md) so `io` can check labels and sizes against the ultrasonic distance.
