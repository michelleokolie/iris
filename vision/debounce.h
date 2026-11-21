// Debounce raw per-frame Alerts so io only gets stable ones (no LED/servo/speech flicker).
// Asymmetric on purpose: warn fast, calm down slowly. Frames are ~126 ms on the Pi.
#pragma once
#include "types.h"

#include <optional>
#include <string>

class Debounce {
public:
    static constexpr int UP_FRAMES = 2;    // level rises: ~0.25 s
    static constexpr int DOWN_FRAMES = 5;  // level falls (incl. back to clear): ~0.6 s
    static constexpr int TURN_FRAMES = 3;  // same level, new direction: ~0.4 s

    // Returns the Alert to send when the stable Alert changes, otherwise nothing.
    std::optional<Alert> update(const Alert& raw);

private:
    Alert sent_{-1, ""};  // nothing sent yet, so the first real Alert counts as "rising"
    int up_ = 0, down_ = 0, turn_ = 0;
    std::string turn_dir_;
};
