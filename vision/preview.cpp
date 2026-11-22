// Screen calls follow QNX's mjpeg_example (camera-projects/applications): context, window, window buffers,
// write pixels, post. Any failure is fatal (preview is opt-in, so a broken display should be loud).
#include "preview.h"

#include "glyphs.h"

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>

static void check(int rc, const char* what) {
    if (rc != 0) {
        std::perror(what);
        std::exit(1);
    }
}

struct Rgb { uint8_t r, g, b; };
static constexpr Rgb LEVEL_COLOUR[4] = {{40, 200, 40}, {150, 150, 150}, {240, 200, 0}, {230, 30, 30}};
static constexpr Rgb GREY{170, 170, 170}, BLUE{60, 120, 255}, WHITE{255, 255, 255}, BLACK{0, 0, 0};
static constexpr float STRIP_LEFT = 0.33f, STRIP_RIGHT = 0.67f;  // same strip as decide.cpp
static constexpr int BAR_H = 22;
static constexpr int TEXT_SCALE = 2;  // 5x7 glyphs drawn at 10x14
static constexpr int GLYPH_W = 6 * TEXT_SCALE, GLYPH_H = 7 * TEXT_SCALE;

Preview::Preview(int width, int height) : w_(width), h_(height) {
    check(screen_create_context(&ctx_, SCREEN_APPLICATION_CONTEXT), "screen_create_context");
    check(screen_create_window(&win_, ctx_), "screen_create_window");
    int format = SCREEN_FORMAT_RGBX8888;  // 32-bit 0xXXRRGGBB: bytes B, G, R, X in memory
    check(screen_set_window_property_iv(win_, SCREEN_PROPERTY_FORMAT, &format), "window format");
    int usage = SCREEN_USAGE_NATIVE | SCREEN_USAGE_WRITE;
    check(screen_set_window_property_iv(win_, SCREEN_PROPERTY_USAGE, &usage), "window usage");
    // The desktop's window manager otherwise resizes the window (stretching the 640x480 image): lay it out
    // ourselves at the image's exact size.
    int self_layout = 1;
    check(screen_set_window_property_iv(win_, SCREEN_PROPERTY_SELF_LAYOUT, &self_layout), "window self layout");
    int size[2] = {w_, h_};
    check(screen_set_window_property_iv(win_, SCREEN_PROPERTY_SIZE, size), "window size");
    check(screen_set_window_property_iv(win_, SCREEN_PROPERTY_SOURCE_SIZE, size), "window source size");
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
                   const Alert& alert, const std::string& note) {
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

    // Text with a filled background, uppercase A-Z, 0-9, '.', '-', space (glyphs.h).
    auto text = [&](int x, int y, const std::string& str, Rgb fg, Rgb bg) {
        for (int yy = y - 2; yy < y + GLYPH_H + 2; ++yy)
            for (int xx = x - 2; xx < x + static_cast<int>(str.size()) * GLYPH_W + 1; ++xx) put(xx, yy, bg);
        for (size_t i = 0; i < str.size(); ++i) {
            const uint8_t* g = glyph(str[i]);
            for (int row = 0; row < 7; ++row)
                for (int col = 0; col < 5; ++col)
                    if (g[row] & (0x10 >> col))
                        for (int dy = 0; dy < TEXT_SCALE; ++dy)
                            for (int dx = 0; dx < TEXT_SCALE; ++dx)
                                put(x + static_cast<int>(i) * GLYPH_W + col * TEXT_SCALE + dx, y + row * TEXT_SCALE + dy, fg);
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
    // Name and score on each box, above its top edge (inside it when there's no room under the bar).
    for (const auto& b : boxes) {
        // name, score, then width and height in % of the frame (what the level thresholds compare against)
        std::string label = std::string(coco_name(std::stoi(b.label))) + " " + std::to_string(static_cast<int>(b.score * 100)) +
                            " W" + std::to_string(static_cast<int>((b.x2 - b.x1) * 100)) + " H" +
                            std::to_string(static_cast<int>((b.y2 - b.y1) * 100));
        int x = static_cast<int>(b.x1 * w_) + 2, y = static_cast<int>(b.y1 * h_) - GLYPH_H - 4;
        if (y < BAR_H + 2) y = std::max(static_cast<int>(b.y1 * h_), BAR_H) + 4;  // no room above: inside the box
        text(x, y, label, WHITE, BLACK);
    }

    // Level bar with a white marker on the free side (centre for "ahead", none for "clear").
    for (int y = 0; y < BAR_H; ++y)
        for (int x = 0; x < w_; ++x) put(x, y, LEVEL_COLOUR[alert.level]);
    int mark = alert.direction == "left" ? w_ / 6 : alert.direction == "right" ? w_ * 5 / 6 : w_ / 2;
    if (alert.direction != "clear")
        for (int y = 3; y < BAR_H - 3; ++y)
            for (int x = mark - 12; x <= mark + 12; ++x) put(x, y, WHITE);
    text(6, (BAR_H - GLYPH_H) / 2, "LEVEL " + std::to_string(alert.level) + " " + alert.direction, BLACK,
         LEVEL_COLOUR[alert.level]);
    if (!note.empty())  // right-aligned, clear of the level text
        text(w_ - static_cast<int>(note.size()) * GLYPH_W - 6, (BAR_H - GLYPH_H) / 2, note, WHITE, BLACK);

    int dirty[4] = {0, 0, w_, h_};
    check(screen_post_window(win_, buf[0], 1, dirty, 0), "screen_post_window");
}
