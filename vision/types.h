// Types shared inside the vision process. See docs/interfaces.md.
#pragma once

#include <cstdint>
#include <string>
#include <vector>

struct Frame { int width, height; std::vector<uint8_t> bgr; };  // HxWx3, BGR, row-major

struct Box { float x1, y1, x2, y2; std::string label; float score; };  // normalized 0..1

struct Alert {
    int level;              // 0=clear, 1=far, 2=near, 3=imminent
    std::string direction;  // "left" | "right" | "ahead" | "clear"
    bool operator==(const Alert& o) const { return level == o.level && direction == o.direction; }
};
