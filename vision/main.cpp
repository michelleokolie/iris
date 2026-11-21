// vision: capture -> detect -> decide -> debounce, sends Alert lines to io over a UNIX socket.
// Usage: ./vision model.onnx [socket_path]
// Without socket_path it only prints (for testing without io running).
// VISION_DEBUG=1 also prints every box and writes /tmp/vision.ppm with boxes drawn.

#include "capture.h"
#include "debounce.h"
#include "decide.h"
#include "detect.h"

#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <optional>
#include <string>

static constexpr camera_unit_t UNIT = CAMERA_UNIT_5;  // C920, see docs/decisions.md
static constexpr int THREADS = 2;                     // no gain past 2, see docs/decisions.md

static int connect_io(const char* path) {
    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    sockaddr_un addr{};
    addr.sun_family = AF_UNIX;
    std::strncpy(addr.sun_path, path, sizeof(addr.sun_path) - 1);
    if (fd < 0 || connect(fd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
        std::perror(path);
        std::exit(1);
    }
    return fd;
}

// Debug only: draw box outlines (red, 2 px) and write the frame as a PPM.
static void write_debug_ppm(Frame frame, const std::vector<Box>& boxes) {
    for (const auto& b : boxes) {
        int x1 = static_cast<int>(b.x1 * frame.width), x2 = static_cast<int>(b.x2 * frame.width);
        int y1 = static_cast<int>(b.y1 * frame.height), y2 = static_cast<int>(b.y2 * frame.height);
        for (int y = std::max(y1, 0); y < std::min(y2, frame.height); ++y)
            for (int x = std::max(x1, 0); x < std::min(x2, frame.width); ++x)
                if (x - x1 < 2 || x2 - x <= 2 || y - y1 < 2 || y2 - y <= 2) {
                    uint8_t* px = &frame.bgr[(static_cast<size_t>(y) * frame.width + x) * 3];
                    px[0] = 0; px[1] = 0; px[2] = 255;
                }
    }
    FILE* f = std::fopen("/tmp/vision.ppm", "wb");
    std::fprintf(f, "P6\n%d %d\n255\n", frame.width, frame.height);
    for (size_t i = 0; i < frame.bgr.size(); i += 3) {
        uint8_t rgb[3] = {frame.bgr[i + 2], frame.bgr[i + 1], frame.bgr[i]};
        std::fwrite(rgb, 1, 3, f);
    }
    std::fclose(f);
}

int main(int argc, char** argv) {
    const bool debug = std::getenv("VISION_DEBUG") != nullptr;
    if (argc != 2 && argc != 3) { std::fprintf(stderr, "usage: %s model.onnx [socket_path]\n", argv[0]); return 1; }
    int fd = argc == 3 ? connect_io(argv[2]) : -1;

    Detector detector(argv[1], THREADS);
    Capture capture(UNIT);
    Debounce debounce;

    for (;;) {
        Frame frame = capture.next();
        auto t0 = std::chrono::steady_clock::now();
        std::vector<Box> boxes = detector.detect(frame);
        Alert alert = decide(boxes);
        auto ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
        std::printf("%6.1f ms  %2zu boxes  %d %s\n", ms, boxes.size(), alert.level, alert.direction.c_str());
        if (debug) {
            for (const auto& b : boxes)
                std::printf("    label %3s  score %.2f  x %.2f-%.2f  y %.2f-%.2f\n", b.label.c_str(), b.score,
                            b.x1, b.x2, b.y1, b.y2);
            write_debug_ppm(frame, boxes);
        }

        std::optional<Alert> stable = debounce.update(alert);
        if (!stable) continue;
        std::printf("  -> send %d %s\n", stable->level, stable->direction.c_str());
        if (fd < 0) continue;
        std::string line = std::to_string(stable->level) + " " + stable->direction + "\n";
        if (write(fd, line.data(), line.size()) != static_cast<ssize_t>(line.size())) {
            std::perror("write to io");
            return 1;
        }
    }
}
