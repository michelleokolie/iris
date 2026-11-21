// Port of PR #3's vision/decide.py. Rules in docs/interfaces.md.
#include "decide.h"

#include <algorithm>
#include <cmath>

static constexpr float STRIP_LEFT = 0.33f;
static constexpr float STRIP_RIGHT = 0.67f;
static constexpr float AHEAD_TOLERANCE = 0.05f;  // fraction of frame width

static bool in_path(const Box& b) { return b.x2 > STRIP_LEFT && b.x1 < STRIP_RIGHT; }

static bool is_close(const Box& b) { return (b.y2 - b.y1) > 0.5f || b.y2 > 0.9f; }

static float occupancy(const std::vector<Box>& boxes, float lo, float hi) {
    float total = 0.0f;
    for (const auto& b : boxes) total += std::max(0.0f, std::min(b.x2, hi) - std::max(b.x1, lo));
    return total;
}

Alert decide(const std::vector<Box>& boxes) {
    int level = 0;
    for (const auto& b : boxes) {
        if (!in_path(b)) continue;
        int l = 1;
        if (is_close(b)) l = b.y2 > 0.9f ? 3 : 2;
        level = std::max(level, l);
    }
    if (level == 0) return {0, "clear"};

    // "ahead" = neither side is clearly freer, i.e. the obstacle is roughly centred.
    // Without a tolerance this needed an exact float tie and practically never fired.
    float left = occupancy(boxes, 0.0f, 0.5f);
    float right = occupancy(boxes, 0.5f, 1.0f);
    if (std::abs(left - right) <= AHEAD_TOLERANCE) return {level, "ahead"};
    return {level, left < right ? "left" : "right"};
}
