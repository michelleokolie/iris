// Runs anywhere:
//   clang++ -std=c++17 debounce_test.cpp debounce.cpp -o debounce_test && ./debounce_test
#include "debounce.h"

#include <cassert>
#include <cstdio>
#include <vector>

// Feed raw Alerts; return what would be sent, in order.
static std::vector<Alert> run(const std::vector<Alert>& raws, Debounce d = Debounce()) {
    std::vector<Alert> sent;
    for (const auto& a : raws)
        if (auto s = d.update(a)) sent.push_back(*s);
    return sent;
}

int main() {
    const Alert clear{0, "clear"}, near_l{2, "left"}, imm_l{3, "left"}, imm_r{3, "right"};
    using V = std::vector<Alert>;

    // Defaults (1, 3, 2): warnings go out on the first frame.
    assert((run({clear}) == V{clear}));
    assert((run({clear, near_l}) == V{clear, near_l}));
    assert((run({clear, near_l, imm_l}) == V{clear, near_l, imm_l}));

    // Red holds through short detector misses (2 clear frames)...
    assert((run({clear, near_l, clear, clear, near_l}) == V{clear, near_l}));
    // ...and clears after 3 clear frames in a row.
    assert((run({clear, near_l, clear, clear, clear}) == V{clear, near_l, clear}));

    // Left/right flip-flopping at the same level doesn't go out; a steady new direction does after 2.
    assert((run({clear, imm_l, imm_r, imm_l, imm_r}) == V{clear, imm_l}));
    assert((run({clear, imm_l, imm_r, imm_r}) == V{clear, imm_l, imm_r}));

    // Slower settings (VISION_DEBOUNCE=2,5,3): one-frame blips never go out, even rising.
    assert((run({clear, clear, near_l, clear}, Debounce(2, 5, 3)) == V{clear}));
    assert((run({clear, clear, imm_l, near_l}, Debounce(2, 5, 3)) == V{clear, near_l}));

    std::puts("debounce_test: all passed");
}
