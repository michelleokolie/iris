# Assistive Vision Wearable (Hack Western 13)

Chest-mounted wearable for blind and low-vision users. Raspberry Pi 5 running QNX detects obstacles (and falls) and tells the wearer what to do: spoken guidance to earbuds (ideal), servo tap + LEDs (MVP). Outdoor/trail focus. Name TBD.

Prize targets: QNX embedded AI (must run on QNX, use an open-source QNX AI module: onnxruntime), Sun Life Health, PCBWay Hardware, Most Adventurous, Gemini (stretch).

## Rules
- No defensive coding. No fallback detectors, no swallowed exceptions, no speculative try/except, no handling of impossible states. Validate only at hardware/user-input boundaries; let everything else crash loudly.
- Keep modules tiny. Only the interfaces in `docs/interfaces.md` cross module boundaries; change that file first if an interface must change.
- One worktree and branch per stream (see `docs/tasks.md`). Never edit files owned by another stream.
- Log decisions in `docs/decisions.md` (one line each) so a cleared session can resume cold.
- Claude cannot touch the board. Hardware results come back from the humans; ask for exact error output.

## Pipeline
capture -> detect (onnxruntime) -> decide -> actuate (servo, LEDs) + speak (audio)

## Hardware
Pi 5 + QNX, 1 USB webcam (MVP; 2nd camera is stretch), servo (tap arm), 4 LEDs (2 blue, 1 red, 1 green), 3-axis accelerometer (I2C), rotary angle sensor (analog, needs Grove Base Hat/ADC), IR reflective sensor (hand-wave trigger), USB-C power bank. Pi 5 has no headphone jack and no analog input. Power the servo from the bank/separate 5V rail, shared ground.

## Context hygiene
`/clear` between streams. Start each stream by reading this file, `docs/interfaces.md`, `docs/tasks.md`.
