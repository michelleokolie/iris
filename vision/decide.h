#pragma once
#include "types.h"

#include <optional>

Alert decide(const std::vector<Box>& boxes);

// The in-path box that drives the Alert: highest level, then tallest. None if nothing is in path.
std::optional<Box> primary_box(const std::vector<Box>& boxes);
