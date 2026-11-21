// Debounce raw per-frame Alerts so io only gets stable ones (no LED/servo/speech flicker).
// Asymmetric on purpose: warn immediately, calm down slowly. Frames are ~126 ms on the Pi.
#pragma once
#include "types.h"

#include <optional>
#include <string>

class Debounce {
public:
    // Consecutive frames needed before sending: level rises / level falls (incl. back to clear) /
    // same level with a new direction. Defaults: 1 (instant) / 3 (~0.4 s) / 2 (~0.25 s).
    Debounce(int up_frames = 1, int down_frames = 3, int turn_frames = 2);

    // Returns the Alert to send when the stable Alert changes, otherwise nothing.
    std::optional<Alert> update(const Alert& raw);

private:
    int up_frames_, down_frames_, turn_frames_;
    Alert sent_{-1, ""};  // nothing sent yet, so the first real Alert counts as "rising"
    int up_ = 0, down_ = 0, turn_ = 0;
    std::string turn_dir_;
};
