"# HackWestern 13 Project" 

## Hardware side (hw/)

Runs on the Pi 5 under QNX 8.0 (Python 3.14, gcc on board). Pin map and unverified items: `docs/decisions.md`.

### Tests (any machine, no hardware)
```
python -m venv venv && venv/Scripts/pip install pytest   # or venv/bin/pip
venv/Scripts/python -m pytest -q
```

### Fake-GPIO demo (no board)
```
python hw/demo_alerts.py --fake
```

### On the board (SSH in, copy the repo over, then from the repo root)
```
cd hw
gcc -o i2cscan i2cscan.c && ./i2cscan /dev/i2c1     # expect "found 0x4c" for the accelerometer
gcc -o accel accel.c && ./accel /dev/i2c1 10        # prints "x y z" raw counts; ctrl-c to stop
python3 bench.py led                                # then: servo | alerts
```

Accelerometer and IR from Python (run from `hw/`):
```
python3 -c "from accel import Accel; a = Accel(); print([a.read() for _ in range(5)])"
python3 -c "from ir_read import IrReader; r = IrReader(); print(r.read())"
```
Flat on its back the accelerometer should read about (0, 0, 1) g. If the IR wave reads inverted, construct `IrReader(active_high=False)`.

Pass `Actuator()`, `HandWave(IrReader().read)` and `Accel().read` into the main loop; `FallDetector.update(t, accel.read())` returns True on a fall.
