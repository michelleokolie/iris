// Port of PR #3's vision/decide.py. Rules in docs/interfaces.md.
#include "decide.h"

#include <algorithm>

static constexpr float STRIP_LEFT = 0.33f;
static constexpr float STRIP_RIGHT = 0.67f;

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

    float left = occupancy(boxes, 0.0f, 0.5f);
    float right = occupancy(boxes, 0.5f, 1.0f);
    if (left < right) return {level, "left"};
    if (right < left) return {level, "right"};
    return {level, "ahead"};
}
