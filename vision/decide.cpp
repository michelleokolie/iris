// Port of PR #3's vision/decide.py. Rules in docs/interfaces.md.
#include "decide.h"

#include <algorithm>
#include <cmath>

static constexpr float STRIP_LEFT = 0.33f;
static constexpr float STRIP_RIGHT = 0.67f;
static constexpr float AHEAD_TOLERANCE = 0.05f;  // fraction of frame width

static bool in_path(const Box& b) { return b.x2 > STRIP_LEFT && b.x1 < STRIP_RIGHT; }

static bool is_close(const Box& b) { return (b.y2 - b.y1) > 0.5f || b.y2 > 0.9f; }

// Height only: where the bottom edge lands depends on camera tilt (a tilted-up camera cuts the feet
// of a person 3-4 m away, so their box touches the bottom), so y2 can't mean "imminent".
static bool is_very_close(const Box& b) { return (b.y2 - b.y1) > 0.8f; }

static float occupancy(const std::vector<Box>& boxes, float lo, float hi) {
    float total = 0.0f;
    for (const auto& b : boxes) total += std::max(0.0f, std::min(b.x2, hi) - std::max(b.x1, lo));
    return total;
}

// Level of one box: 0 if not in path, else 1 far / 2 near / 3 imminent.
static int box_level(const Box& b) {
    if (!in_path(b)) return 0;
    if (is_very_close(b)) return 3;
    return is_close(b) ? 2 : 1;
}

std::optional<Box> primary_box(const std::vector<Box>& boxes) {
    std::optional<Box> best;
    for (const auto& b : boxes) {
        int l = box_level(b);
        if (l == 0) continue;
        if (!best || l > box_level(*best) || (l == box_level(*best) && b.y2 - b.y1 > best->y2 - best->y1)) best = b;
    }
    return best;
}

Alert decide(const std::vector<Box>& boxes) {
    std::optional<Box> closest = primary_box(boxes);  // most urgent in-path box, then tallest (= closest)
    if (!closest) return {0, "clear"};
    int level = box_level(*closest);

    // Steer away from the closest obstacle: a far table on one side must not outweigh a person right in front.
    float centre = (closest->x1 + closest->x2) / 2;
    if (centre < 0.5f - AHEAD_TOLERANCE) return {level, "right"};
    if (centre > 0.5f + AHEAD_TOLERANCE) return {level, "left"};

    // Closest obstacle roughly centred: pick the side with more free space over all boxes; "ahead" if neither
    // side is clearly freer (without a tolerance an exact float tie practically never fired).
    float left = occupancy(boxes, 0.0f, 0.5f);
    float right = occupancy(boxes, 0.5f, 1.0f);
    if (std::abs(left - right) <= AHEAD_TOLERANCE) return {level, "ahead"};
    return {level, left < right ? "left" : "right"};
}
