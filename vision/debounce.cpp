#include "debounce.h"

Debounce::Debounce(int up_frames, int down_frames, int turn_frames)
    : up_frames_(up_frames), down_frames_(down_frames), turn_frames_(turn_frames) {}

std::optional<Alert> Debounce::update(const Alert& raw) {
    bool ready = false;
    if (raw.level > sent_.level) {
        // Count frames that are more urgent than what's sent, whatever their exact level or
        // direction, so a flickering "2 left"/"3 right" still escalates.
        down_ = turn_ = 0;
        ready = ++up_ >= up_frames_;
    } else if (raw.level < sent_.level) {
        up_ = turn_ = 0;
        ready = ++down_ >= down_frames_;
    } else {
        up_ = down_ = 0;
        if (raw.direction == sent_.direction) {
            turn_ = 0;
        } else {
            turn_ = raw.direction == turn_dir_ ? turn_ + 1 : 1;
            turn_dir_ = raw.direction;
            ready = turn_ >= turn_frames_;
        }
    }
    if (!ready) return std::nullopt;

    sent_ = raw;  // send the latest frame's level and direction
    up_ = down_ = turn_ = 0;
    return raw;
}
