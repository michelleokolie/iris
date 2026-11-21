#include "capture.h"

#include <algorithm>
#include <cstdio>
#include <cstdlib>

static void check(camera_error_t err, const char* what) {
    if (err != CAMERA_EOK) {
        std::fprintf(stderr, "%s failed: camera_error_t=%d\n", what, static_cast<int>(err));
        std::exit(1);
    }
}

static uint8_t clamp8(int v) { return static_cast<uint8_t>(std::clamp(v, 0, 255)); }

// YUYV (Y0 Cb Y1 Cr), BT.601 limited range -> BGR.
static void ycbycr_to_bgr(const uint8_t* src, int w, int h, int stride, uint8_t* dst) {
    for (int y = 0; y < h; ++y) {
        const uint8_t* row = src + static_cast<size_t>(y) * stride;
        for (int x = 0; x < w; ++x) {
            int Y = 298 * (row[x * 2] - 16) + 128;
            int cb = row[(x & ~1) * 2 + 1] - 128;
            int cr = row[(x & ~1) * 2 + 3] - 128;
            uint8_t* px = dst + (static_cast<size_t>(y) * w + x) * 3;
            px[0] = clamp8((Y + 516 * cb) >> 8);
            px[1] = clamp8((Y - 100 * cb - 208 * cr) >> 8);
            px[2] = clamp8((Y + 409 * cr) >> 8);
        }
    }
}

Capture::Capture(camera_unit_t unit) {
    uint32_t mode = CAMERA_MODE_DREAD | CAMERA_MODE_PREAD | CAMERA_MODE_PWRITE;
    check(camera_open(unit, mode, &cam_), "camera_open");
    check(camera_start_viewfinder(cam_, on_frame, nullptr, this), "camera_start_viewfinder");
}

Capture::~Capture() {
    check(camera_stop_viewfinder(cam_), "camera_stop_viewfinder");
    check(camera_close(cam_), "camera_close");
}

void Capture::on_frame(camera_handle_t, camera_buffer_t* buf, void* arg) {
    auto* self = static_cast<Capture*>(arg);
    if (buf->frametype != CAMERA_FRAMETYPE_YCBYCR) {  // C920 default, see docs/decisions.md
        std::fprintf(stderr, "unexpected frametype %d\n", static_cast<int>(buf->frametype));
        std::exit(1);
    }
    const auto& d = buf->framedesc.ycbycr;
    int w = static_cast<int>(d.width), h = static_cast<int>(d.height);

    std::lock_guard<std::mutex> lock(self->mu_);
    self->latest_.width = w;
    self->latest_.height = h;
    self->latest_.bgr.resize(static_cast<size_t>(w) * h * 3);
    ycbycr_to_bgr(static_cast<const uint8_t*>(buf->framebuf), w, h, static_cast<int>(d.stride),
                  self->latest_.bgr.data());
    ++self->seq_;
    self->cv_.notify_one();
}

Frame Capture::next() {
    std::unique_lock<std::mutex> lock(mu_);
    cv_.wait(lock, [this] { return seq_ != taken_; });
    taken_ = seq_;
    return latest_;
}
