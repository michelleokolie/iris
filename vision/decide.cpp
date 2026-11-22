// Port of PR #3's vision/decide.py. Rules in docs/interfaces.md.
#include "decide.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>

static constexpr float STRIP_LEFT = 0.33f;
static constexpr float STRIP_RIGHT = 0.67f;
static constexpr float AHEAD_TOLERANCE = 0.05f;  // fraction of frame width

static bool in_path(const Box& b) { return b.x2 > STRIP_LEFT && b.x1 < STRIP_RIGHT; }

// Box size (fraction of the frame) is the camera's stand-in for distance; never where the bottom edge lands,
// which depends on camera tilt. Height alone can't do it for people: a standing person is taller than the view
// from a few metres away, so their box is ~0.9-1.0 tall at 2.5 m and at 0.5 m alike. Width keeps shrinking with
// distance (a ~0.45 m wide person: ~0.4 of the frame at 1 m, ~0.2 at 2 m), so warnings need both:
//   level 1: taller than `far`                      (smaller boxes don't count: the path reads clear)
//   level 2: taller than `close` and wider than `close_w`
//   level 3: taller than `very_close` and wider than `very_close_w`
// Biased against false alarms: a warning that is always on gets ignored.
// VISION_LEVELS=far,close,very_close,close_w,very_close_w overrides the defaults for tuning on the board.
static LevelThresholds read_levels() {
    LevelThresholds t{0.25f, 0.5f, 0.8f, 0.2f, 0.4f};
    if (const char* e = std::getenv("VISION_LEVELS"))
        std::sscanf(e, "%f,%f,%f,%f,%f", &t.far, &t.close, &t.very_close, &t.close_w, &t.very_close_w);
    return t;
}
static const LevelThresholds LEVELS = read_levels();

LevelThresholds level_thresholds() { return LEVELS; }

static float occupancy(const std::vector<Box>& boxes, float lo, float hi) {
    float total = 0.0f;
    for (const auto& b : boxes) total += std::max(0.0f, std::min(b.x2, hi) - std::max(b.x1, lo));
    return total;
}

// Level of one box: 0 if not in path, else 1 far / 2 near / 3 imminent.
static int box_level(const Box& b) {
    if (!in_path(b)) return 0;
    float h = b.y2 - b.y1, w = b.x2 - b.x1;
    if (h > LEVELS.very_close && w > LEVELS.very_close_w) return 3;
    if (h > LEVELS.close && w > LEVELS.close_w) return 2;
    return h > LEVELS.far ? 1 : 0;
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
