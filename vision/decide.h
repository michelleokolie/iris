#pragma once
#include "types.h"

#include <optional>

Alert decide(const std::vector<Box>& boxes);

// In-path box-height thresholds (fraction of the frame) for levels 1/2/3; VISION_LEVELS=far,close,very_close.
struct LevelThresholds { float far, close, very_close; };
LevelThresholds level_thresholds();

// The in-path box that drives the Alert: highest level, then tallest. None if nothing is in path.
std::optional<Box> primary_box(const std::vector<Box>& boxes);
