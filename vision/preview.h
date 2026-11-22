// preview: optional live window on the Pi's screen (visible over VNC) showing what vision sees and decides.
// Debug/demo only, enabled with VISION_PREVIEW=1. Draws the camera frame, every detection box (the one driving
// the Alert thick, in its level's colour; the rest thin grey), the in-path strip, and a level bar on top with a
// white marker on the free side.
#pragma once
#include "types.h"

#include <screen/screen.h>

#include <optional>
#include <string>
#include <vector>

class Preview {
public:
    Preview(int width, int height);
    // note: extra text for the bar, e.g. the ultrasonic reading ("US 398CM"); empty for none.
    void show(const Frame& frame, const std::vector<Box>& boxes, const std::optional<Box>& primary,
              const Alert& alert, const std::string& note);

private:
    screen_context_t ctx_ = nullptr;
    screen_window_t win_ = nullptr;
    int w_, h_;
};
