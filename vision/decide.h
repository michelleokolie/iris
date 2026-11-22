#pragma once
#include "types.h"

#include <optional>

Alert decide(const std::vector<Box>& boxes);

// In-path box size thresholds (fractions of the frame): heights for levels 1/2/3, widths for 2/3.
// VISION_LEVELS=far,close,very_close,close_w,very_close_w.
struct LevelThresholds { float far, close, very_close, close_w, very_close_w; };
LevelThresholds level_thresholds();

// The in-path box that drives the Alert: highest level, then tallest. None if nothing is in path.
std::optional<Box> primary_box(const std::vector<Box>& boxes);
