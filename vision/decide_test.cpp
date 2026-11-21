// Same cases as PR #3's tests/test_decide.py. Runs anywhere:
//   clang++ -std=c++17 decide_test.cpp decide.cpp -o decide_test && ./decide_test
#include "decide.h"

#include <cassert>
#include <cstdio>

static Box box(float x1, float y1, float x2, float y2) { return {x1, y1, x2, y2, "person", 0.9f}; }

int main() {
    assert((decide({}) == Alert{0, "clear"}));
    assert((decide({box(0.0f, 0.2f, 0.2f, 0.4f)}) == Alert{0, "clear"}));
    assert(decide({box(0.4f, 0.3f, 0.6f, 0.5f)}).level == 1);
    assert(decide({box(0.4f, 0.1f, 0.6f, 0.8f)}).level == 2);
    assert(decide({box(0.4f, 0.5f, 0.6f, 0.95f)}).level == 3);
    assert(decide({box(0.0f, 0.3f, 0.45f, 0.5f), box(0.4f, 0.3f, 0.6f, 0.5f)}).direction == "right");
    assert(decide({box(0.55f, 0.3f, 1.0f, 0.5f), box(0.4f, 0.3f, 0.6f, 0.5f)}).direction == "left");
    std::puts("decide_test: all passed");
}
