// Screen calls follow QNX's mjpeg_example (camera-projects/applications): context, window, window buffers,
// write pixels, post. Any failure is fatal (preview is opt-in, so a broken display should be loud).
#include "preview.h"

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>

static void check(int rc, const char* what) {
    if (rc != 0) {
        std::perror(what);
        std::exit(1);
    }
}

struct Rgb { uint8_t r, g, b; };
static constexpr Rgb LEVEL_COLOUR[4] = {{40, 200, 40}, {150, 150, 150}, {240, 200, 0}, {230, 30, 30}};
static constexpr Rgb GREY{170, 170, 170}, BLUE{60, 120, 255}, WHITE{255, 255, 255};
static constexpr float STRIP_LEFT = 0.33f, STRIP_RIGHT = 0.67f;  // same strip as decide.cpp
static constexpr int BAR_H = 18;

Preview::Preview(int width, int height) : w_(width), h_(height) {
    check(screen_create_context(&ctx_, SCREEN_APPLICATION_CONTEXT), "screen_create_context");
    check(screen_create_window(&win_, ctx_), "screen_create_window");
    int format = SCREEN_FORMAT_RGBX8888;  // 32-bit 0xXXRRGGBB: bytes B, G, R, X in memory
    check(screen_set_window_property_iv(win_, SCREEN_PROPERTY_FORMAT, &format), "window format");
    int usage = SCREEN_USAGE_NATIVE | SCREEN_USAGE_WRITE;
    check(screen_set_window_property_iv(win_, SCREEN_PROPERTY_USAGE, &usage), "window usage");
    int size[2] = {w_, h_};
    check(screen_set_window_property_iv(win_, SCREEN_PROPERTY_SIZE, size), "window size");
    check(screen_set_window_property_iv(win_, SCREEN_PROPERTY_BUFFER_SIZE, size), "buffer size");
    const char id[] = "iris-vision";
    check(screen_set_window_property_cv(win_, SCREEN_PROPERTY_ID_STRING, sizeof(id), id), "window id");
    // On top of the desktop (its wallpaper is a window too, so a default z-order leaves us hidden), visible,
    // just below the taskbar.
    int zorder = 1000;
    check(screen_set_window_property_iv(win_, SCREEN_PROPERTY_ZORDER, &zorder), "window zorder");
    int visible = 1;
    check(screen_set_window_property_iv(win_, SCREEN_PROPERTY_VISIBLE, &visible), "window visible");
    int pos[2] = {0, 48};
    check(screen_set_window_property_iv(win_, SCREEN_PROPERTY_POSITION, pos), "window position");
    check(screen_create_window_buffers(win_, 2), "screen_create_window_buffers");
}

void Preview::show(const Frame& frame, const std::vector<Box>& boxes, const std::optional<Box>& primary,
                   const Alert& alert) {
    screen_buffer_t buf[2];
    check(screen_get_window_property_pv(win_, SCREEN_PROPERTY_RENDER_BUFFERS, reinterpret_cast<void**>(buf)),
          "render buffers");
    void* ptr = nullptr;
    int stride = 0;
    check(screen_get_buffer_property_pv(buf[0], SCREEN_PROPERTY_POINTER, &ptr), "buffer pointer");
    check(screen_get_buffer_property_iv(buf[0], SCREEN_PROPERTY_STRIDE, &stride), "buffer stride");
    auto* px = static_cast<uint8_t*>(ptr);

    auto put = [&](int x, int y, Rgb c) {
        if (x < 0 || y < 0 || x >= w_ || y >= h_) return;
        uint8_t* p = px + static_cast<size_t>(y) * stride + static_cast<size_t>(x) * 4;
        p[0] = c.b; p[1] = c.g; p[2] = c.r; p[3] = 255;
    };
    auto rect = [&](const Box& b, int thick, Rgb c) {
        int x1 = static_cast<int>(b.x1 * w_), x2 = static_cast<int>(b.x2 * w_) - 1;
        int y1 = static_cast<int>(b.y1 * h_), y2 = static_cast<int>(b.y2 * h_) - 1;
        for (int t = 0; t < thick; ++t) {
            for (int x = x1; x <= x2; ++x) { put(x, y1 + t, c); put(x, y2 - t, c); }
            for (int y = y1; y <= y2; ++y) { put(x1 + t, y, c); put(x2 - t, y, c); }
        }
    };

    // Camera frame (BGR) -> window (B, G, R, X).
    for (int y = 0; y < h_; ++y) {
        const uint8_t* src = &frame.bgr[static_cast<size_t>(y) * frame.width * 3];
        uint8_t* dst = px + static_cast<size_t>(y) * stride;
        for (int x = 0; x < w_; ++x) {
            dst[x * 4] = src[x * 3]; dst[x * 4 + 1] = src[x * 3 + 1]; dst[x * 4 + 2] = src[x * 3 + 2]; dst[x * 4 + 3] = 255;
        }
    }

    // In-path strip, every detection thin grey, the box driving the Alert thick in the level colour.
    for (float sx : {STRIP_LEFT, STRIP_RIGHT})
        for (int y = BAR_H; y < h_; ++y) put(static_cast<int>(sx * w_), y, BLUE);
    for (const auto& b : boxes) rect(b, 2, GREY);
    if (primary) rect(*primary, 4, LEVEL_COLOUR[alert.level]);

    // Level bar with a white marker on the free side (centre for "ahead", none for "clear").
    for (int y = 0; y < BAR_H; ++y)
        for (int x = 0; x < w_; ++x) put(x, y, LEVEL_COLOUR[alert.level]);
    int mark = alert.direction == "left" ? w_ / 6 : alert.direction == "right" ? w_ * 5 / 6 : w_ / 2;
    if (alert.direction != "clear")
        for (int y = 3; y < BAR_H - 3; ++y)
            for (int x = mark - 12; x <= mark + 12; ++x) put(x, y, WHITE);

    int dirty[4] = {0, 0, w_, h_};
    check(screen_post_window(win_, buf[0], 1, dirty, 0), "screen_post_window");
}
