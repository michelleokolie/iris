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

To hear the warnings on a phone: put the phone on the same Wi-Fi as the Pi, open `http://<pi address>:8080/` in its browser (the address is the `inet` line of `ifconfig bcm0` on the Pi), tap Start once, and keep the page open and the screen on. `io` serves the page.

`io` needs the built `hw/accel` next to `io_main.py`: `sudo python3 hw/io_main.py` reads the accelerometer in a thread and prints "Fall detected" when `fall.py` sees a jolt, a tilt and then stillness. Flat on its back the accelerometer should read about 1 g on one axis. The IR reader (`ir_read.py`) is unverified: `python3 -c "from ir_read import IrReader; print(IrReader().read())"`; if the wave reads inverted, construct `IrReader(active_high=False)`.
