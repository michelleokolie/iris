// Grab one frame from the sensor service and write it to /tmp.
// API usage follows gitlab.com/qnx/projects/camera-projects/applications/
// camera-dump-frame-no-screen (callback mode) and mjpeg_example (open mode, JPEG buffers).
//
// Prints width/height/frametype, then writes:
//   JPEG     -> /tmp/frame.jpg (bytes as received)
//   YCBYCR   -> /tmp/frame.ppm (YUYV converted to RGB)
//   BGR8888  -> /tmp/frame.ppm
// Any other frametype aborts and prints its number (look it up in camera_api.h).

#include <camera/camera_api.h>

#include <algorithm>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <future>
#include <vector>

static constexpr camera_unit_t UNIT = CAMERA_UNIT_5;  // C920, see docs/decisions.md

static void check(camera_error_t err, const char* what) {
    if (err != CAMERA_EOK) {
        std::fprintf(stderr, "%s failed: camera_error_t=%d\n", what, static_cast<int>(err));
        std::exit(1);
    }
}

static void write_file(const char* path, const void* data, size_t size) {
    FILE* f = std::fopen(path, "wb");
    if (f == nullptr) { std::perror(path); std::exit(1); }
    std::fwrite(data, 1, size, f);
    std::fclose(f);
    std::printf("wrote %s (%zu bytes)\n", path, size);
}

static void write_ppm(const char* path, int w, int h, const std::vector<uint8_t>& rgb) {
    FILE* f = std::fopen(path, "wb");
    if (f == nullptr) { std::perror(path); std::exit(1); }
    std::fprintf(f, "P6\n%d %d\n255\n", w, h);
    std::fwrite(rgb.data(), 1, rgb.size(), f);
    std::fclose(f);
    std::printf("wrote %s\n", path);
}

static uint8_t clamp8(int v) { return static_cast<uint8_t>(std::clamp(v, 0, 255)); }

// YUYV (Y0 Cb Y1 Cr), BT.601 limited range.
static std::vector<uint8_t> ycbycr_to_rgb(const uint8_t* src, int w, int h, int stride) {
    std::vector<uint8_t> rgb(static_cast<size_t>(w) * h * 3);
    for (int y = 0; y < h; ++y) {
        const uint8_t* row = src + static_cast<size_t>(y) * stride;
        for (int x = 0; x < w; ++x) {
            int Y = row[x * 2] - 16;
            int cb = row[(x & ~1) * 2 + 1] - 128;
            int cr = row[(x & ~1) * 2 + 3] - 128;
            uint8_t* px = &rgb[(static_cast<size_t>(y) * w + x) * 3];
            px[0] = clamp8((298 * Y + 409 * cr + 128) >> 8);
            px[1] = clamp8((298 * Y - 100 * cb - 208 * cr + 128) >> 8);
            px[2] = clamp8((298 * Y + 516 * cb + 128) >> 8);
        }
    }
    return rgb;
}

static std::vector<uint8_t> bgra_to_rgb(const uint8_t* src, int w, int h, int stride) {
    std::vector<uint8_t> rgb(static_cast<size_t>(w) * h * 3);
    for (int y = 0; y < h; ++y) {
        const uint8_t* row = src + static_cast<size_t>(y) * stride;
        for (int x = 0; x < w; ++x) {
            uint8_t* px = &rgb[(static_cast<size_t>(y) * w + x) * 3];
            px[0] = row[x * 4 + 2];
            px[1] = row[x * 4 + 1];
            px[2] = row[x * 4 + 0];
        }
    }
    return rgb;
}

static constexpr int SKIP_FRAMES = 30;  // ~1 s at 30 fps, lets auto-exposure settle

struct Ctx {
    std::atomic<int> seen{0};
    std::promise<void> done;
};

static void on_frame(camera_handle_t, camera_buffer_t* buf, void* arg) {
    auto* ctx = static_cast<Ctx*>(arg);
    if (ctx->seen.fetch_add(1) != SKIP_FRAMES) return;  // save exactly one frame

    const uint8_t* data = static_cast<const uint8_t*>(buf->framebuf);
    switch (buf->frametype) {
    case CAMERA_FRAMETYPE_JPEG:
        std::printf("frametype JPEG, %llu bytes\n",
                    static_cast<unsigned long long>(buf->framedesc.jpeg.bufsize));
        write_file("/tmp/frame.jpg", data, buf->framedesc.jpeg.bufsize);
        break;
    case CAMERA_FRAMETYPE_YCBYCR: {
        const auto& d = buf->framedesc.ycbycr;
        std::printf("frametype YCBYCR, %ux%u, stride %u\n", d.width, d.height, d.stride);
        write_ppm("/tmp/frame.ppm", d.width, d.height, ycbycr_to_rgb(data, d.width, d.height, d.stride));
        break;
    }
    case CAMERA_FRAMETYPE_BGR8888: {
        const auto& d = buf->framedesc.bgr8888;
        std::printf("frametype BGR8888, %ux%u, stride %u\n", d.width, d.height, d.stride);
        write_ppm("/tmp/frame.ppm", d.width, d.height, bgra_to_rgb(data, d.width, d.height, d.stride));
        break;
    }
    default:
        std::fprintf(stderr, "unhandled frametype %d\n", static_cast<int>(buf->frametype));
        std::exit(1);
    }
    ctx->done.set_value();
}

int main() {
    camera_handle_t cam = CAMERA_HANDLE_INVALID;
    uint32_t mode = CAMERA_MODE_DREAD | CAMERA_MODE_PREAD | CAMERA_MODE_PWRITE;
    check(camera_open(UNIT, mode, &cam), "camera_open");

    Ctx ctx;
    auto done = ctx.done.get_future();
    check(camera_start_viewfinder(cam, on_frame, nullptr, &ctx), "camera_start_viewfinder");
    done.wait();

    check(camera_stop_viewfinder(cam), "camera_stop_viewfinder");
    check(camera_close(cam), "camera_close");
    return 0;
}
