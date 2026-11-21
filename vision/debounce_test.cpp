// Runs anywhere:
//   clang++ -std=c++17 debounce_test.cpp debounce.cpp -o debounce_test && ./debounce_test
#include "debounce.h"

#include <cassert>
#include <cstdio>
#include <vector>

// Feed raw Alerts; return what would be sent, in order.
static std::vector<Alert> run(const std::vector<Alert>& raws) {
    Debounce d;
    std::vector<Alert> sent;
    for (const auto& a : raws)
        if (auto s = d.update(a)) sent.push_back(*s);
    return sent;
}

int main() {
    const Alert clear{0, "clear"}, near_l{2, "left"}, near_r{2, "right"}, imm_l{3, "left"}, imm_r{3, "right"};

    // Startup: clear goes out after UP_FRAMES (first Alert counts as rising from nothing).
    assert((run({clear, clear}) == std::vector<Alert>{clear}));

    // A single-frame blip never goes out.
    assert((run({clear, clear, near_l, clear, clear}) == std::vector<Alert>{clear}));

    // Escalation is fast: 2 frames.
    assert((run({clear, clear, near_l, near_l}) == std::vector<Alert>{clear, near_l}));

    // Escalation still happens when level/direction flicker between frames (hand in front).
    assert((run({clear, clear, imm_l, near_r}) == std::vector<Alert>{clear, near_r}));

    // Red holds through short detector misses (fewer than DOWN_FRAMES clear frames).
    assert((run({clear, clear, near_l, near_l, clear, clear, clear, near_l}) == std::vector<Alert>{clear, near_l}));

    // ...and clears after DOWN_FRAMES clear frames in a row.
    assert((run({clear, clear, near_l, near_l, clear, clear, clear, clear, clear}) ==
            std::vector<Alert>{clear, near_l, clear}));

    // Left/right flip-flopping at the same level doesn't go out.
    assert((run({clear, clear, imm_l, imm_l, imm_r, imm_l, imm_r, imm_l, imm_r}) ==
            std::vector<Alert>{clear, imm_l}));

    // A steady new direction does, after TURN_FRAMES.
    assert((run({clear, clear, imm_l, imm_l, imm_r, imm_r, imm_r}) == std::vector<Alert>{clear, imm_l, imm_r}));

    std::puts("debounce_test: all passed");
}
