"# HackWestern 13 Project" 

## Hardware side (hw/)

Runs on the Pi 5 under QNX 8.0 (Python 3.14, gcc on board). Pin map and unverified items: `docs/decisions.md`.

### On the board (SSH in, copy the repo over, then from the repo root)
```
cd hw
gcc -o i2cscan i2cscan.c && sudo ./i2cscan /dev/i2c1     # expect "found 0x4c" for the accelerometer
gcc -o accel accel.c && sudo ./accel /dev/i2c1 10        # prints "x y z" raw counts; ctrl-c to stop
sudo python3 bench.py led                                # then: servo | alerts
```

To hear the warnings on a phone (and through AirPods paired to it): the Pi has no Bluetooth on QNX, so `io` serves a page and the phone speaks.
1. Put the phone on the same Wi-Fi as the Pi (the venue Wi-Fi works; no hotspot needed). If the page will not load while the Pi answers ssh, the network may block devices from talking to each other: then use a phone hotspot and put its name and password in `boot/wpa_supplicant.conf`.
2. Find the Pi's address: the `inet` line of `ifconfig bcm0` on the Pi.
3. Start `io` on the Pi. On the phone open `http://<pi address>:8080/` in the browser and tap **Start speaking**; **Test voice** speaks a sample. The page shows Connected / Reconnecting and the last sentence in large text.
4. Keep the page open and the screen on. The page asks the phone to stay awake, but that request only works in secure contexts (this page is plain http), so the screen may still sleep; phones may also stop speech when the screen locks. It has spoken the sentences on one phone (the team's); other phones and a locking screen are untested.

`io` needs the built `hw/accel` next to `io_main.py`: `sudo python3 hw/io_main.py` reads the accelerometer in a thread and prints "Fall detected" when `fall.py` sees a jolt, a tilt and then stillness. Flat on its back the accelerometer should read about 1 g on one axis. The IR reader (`ir_read.py`) is unverified: `python3 -c "from ir_read import IrReader; print(IrReader().read())"`; if the wave reads inverted, construct `IrReader(active_high=False)`.

## Run everything (`hw/run.sh`)
Build once on the Pi (from the repo root; the ultrasonic line needs `~/qnx-rpi` built, see docs/decisions.md):
```
gcc -o hw/accel hw/accel.c
clang++ -std=c++17 -O2 hw/ultrasonic.cpp -o hw/ultrasonic -I$HOME/qnx-rpi/common/system/gpio -I$HOME/qnx-rpi/common/rpi_gpio/public -L$HOME/qnx-rpi/common/rpi_gpio/build/aarch64le-debug -lrpi_gpio -lm -lsocket
cd vision && clang++ -std=c++17 -O2 main.cpp capture.cpp detect.cpp decide.cpp debounce.cpp preview.cpp -o vision -lcamapi -lonnxruntime -lsocket -lscreen
```
Then `sudo sh hw/run.sh` starts io, vision and the reader, restarts any that dies (1 s later) and stops everything on Ctrl-C. Model: `/data/home/qnxuser/capture/deimv2_femto.onnx`, or `sudo env IRIS_MODEL=/path/model.onnx sh hw/run.sh`. Logs: `/tmp/iris/{io,vision,ultrasonic}.log`. More than 5 exits of one process in 30 s prints a FAULT line, stops everything and exits 1. Vision needs about 12 s to load after each start; io says "Camera lost" meanwhile. A stop waits for every program (the reader must run its GPIO cleanup, so it is never killed with SIGKILL).

Starting at boot is not set up. It would mean adding a script under `/system/etc/startup/` on the Pi's QNX image that runs `sh <repo>/hw/run.sh` as root once the network and sensor framework are up; that edits system files, so it needs the owner's go-ahead.
