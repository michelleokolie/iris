# Assistive Vision Wearable (Hack Western 13)

Chest-mounted wearable for blind and low-vision users. Raspberry Pi 5 running QNX detects obstacles and tells the wearer what to do: spoken guidance to earbuds (ideal), servo tap + LEDs (MVP). Outdoor/trail focus. Name TBD.

Prize targets: QNX embedded AI (must run on QNX, use an open-source QNX AI module: onnxruntime), Sun Life Health, PCBWay Hardware, Most Adventurous, Gemini (stretch).

## Rules
- No defensive coding. No fallback detectors, no swallowed exceptions, no speculative try/except, no handling of impossible states. Validate only at hardware/user-input boundaries; let everything else crash loudly.
- Keep modules tiny. Only the interfaces in `docs/interfaces.md` cross module boundaries; change that file first if an interface must change.
- Code layout: `hw/` (the io process, the ultrasonic reader, hardware helpers) and `vision/` (C++ vision); docs in `docs/`. Do not create `src/` or `tests/` folders (the test suite was removed on purpose); new code goes in the folder of its stream.
- One worktree and branch per stream (see `docs/tasks.md`). Never edit files owned by another stream.
- Log decisions in `docs/decisions.md` (one line each) so a cleared session can resume cold.
- Claude may run read-only and bench-test commands on the board over SSH (key auth) once the human has wired a part. Powering down and wiring stay with the human; ask for exact error output when something fails.

## Pipeline
vision (C++): capture -> detect (onnxruntime) -> decide --Alert over /tmp/iris.sock--> io (Python): fuse -> actuate (servo, LEDs) + speak (audio)
ultrasonic (C++, hw/ultrasonic.cpp) --Range over /tmp/iris.sock--> io (Python): fuse

## Hardware
Pi 5 + QNX, 1 USB webcam (MVP; 2nd camera is stretch), servo (tap arm), 2 LEDs (1 red, 1 green), rotary angle sensor (analog, needs Grove Base Hat/ADC), IR reflective sensor (hand-wave trigger), USB-C power bank. Pi 5 has no headphone jack and no analog input. Power the servo from the bank/separate 5V rail, shared ground.

## Context hygiene
`/clear` between streams. Start each stream by reading this file, `docs/interfaces.md`, `docs/tasks.md`.
