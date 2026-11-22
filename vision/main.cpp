// vision: capture -> detect -> decide -> debounce, sends Alert lines to io over a UNIX socket.
// Usage: ./vision model.onnx [socket_path]
// Without socket_path it only prints (for testing without io running).
// VISION_DEBUG=1 also prints every box and writes /tmp/vision.ppm with boxes drawn.
// VISION_DEBOUNCE=up,down,turn overrides the debounce frame counts (default 1,3,2) for tuning.
// VISION_LEVELS=far,close,very_close,close_w,very_close_w overrides the in-path box sizes for the levels
// (default 0.25,0.5,0.8,0.2,0.4: heights for 1/2/3, widths for 2/3).
// VISION_PREVIEW=1 opens a live window on the Pi's screen (VNC): frame, boxes, in-path strip, level bar.

#include "capture.h"
#include "debounce.h"
#include "decide.h"
#include "detect.h"
#include "preview.h"

#include <poll.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#include <algorithm>
#include <cerrno>
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

// write() may send less than asked or be interrupted; loop so a line is never truncated.
static void send_line(int fd, const std::string& line) {
    size_t sent = 0;
    while (sent < line.size()) {
        ssize_t n = write(fd, line.data() + sent, line.size() - sent);
        if (n < 0 && errno == EINTR) continue;
        if (n < 0) {
            std::perror("write to io");
            std::exit(1);
        }
        sent += static_cast<size_t>(n);
    }
}

// "box <label> <x1> <y1> <x2> <y2>" for the box driving the Alert, "box none" if nothing is in path.
// Sent every frame, independent of the debounce, so io has fresh geometry for size/label checks.
static std::string box_line(const std::optional<Box>& b) {
    if (!b) return "box none\n";
    char buf[96];
    // Six decimals: with three, a thin box (x1 = 0.9996, x2 = 0.9998) rounds to zero width and io rejects it.
    std::snprintf(buf, sizeof(buf), "box %s %.6f %.6f %.6f %.6f\n", b->label.c_str(), b->x1, b->y1, b->x2, b->y2);
    return buf;
}

// SAMPLE (display only): io copies each ultrasonic "range <cm> <closing>" / "range none" line back to vision
// over the same socket. Read whatever has arrived without blocking and keep the newest, for the preview bar.
struct RangeNote {
    std::string buf;
    std::string text = "US -";  // shown when nothing has arrived yet or the newest is stale
    std::chrono::steady_clock::time_point at{};

    void poll_from(int fd) {
        pollfd p{fd, POLLIN, 0};
        while (::poll(&p, 1, 0) > 0 && (p.revents & POLLIN)) {
            char chunk[512];
            ssize_t n = read(fd, chunk, sizeof(chunk));
            if (n <= 0) break;
            buf.append(chunk, static_cast<size_t>(n));
        }
        for (size_t nl; (nl = buf.find('\n')) != std::string::npos; buf.erase(0, nl + 1)) {
            std::string line = buf.substr(0, nl);
            float cm = 0, closing = 0;
            if (line == "range none") text = "US NONE";
            else if (std::sscanf(line.c_str(), "range %f %f", &cm, &closing) == 2) text = "US " + std::to_string(static_cast<int>(cm)) + "CM";
            else continue;  // a copy cut short by io's non-blocking send: skip it (display only)
            at = std::chrono::steady_clock::now();
        }
    }
    std::string current() const {
        return std::chrono::steady_clock::now() - at > std::chrono::milliseconds(500) ? "US -" : text;
    }
};

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
    int up = 1, down = 3, turn = 2;
    if (const char* d = std::getenv("VISION_DEBOUNCE")) std::sscanf(d, "%d,%d,%d", &up, &down, &turn);
    std::printf("debounce frames: up %d, down %d, turn %d\n", up, down, turn);
    LevelThresholds lv = level_thresholds();
    std::printf("levels: 1 if h > %.2f; 2 if h > %.2f and w > %.2f; 3 if h > %.2f and w > %.2f\n", lv.far, lv.close,
                lv.close_w, lv.very_close, lv.very_close_w);
    Debounce debounce(up, down, turn);
    const bool preview_on = std::getenv("VISION_PREVIEW") != nullptr;
    std::optional<Preview> preview;  // created on the first frame, which gives its size
    RangeNote range_note;  // SAMPLE: ultrasonic reading for the preview bar, copied over by io

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

        std::optional<Box> primary = primary_box(boxes);
        if (preview_on) {
            if (!preview) preview.emplace(frame.width, frame.height);
            if (fd >= 0) range_note.poll_from(fd);
            preview->show(frame, boxes, primary, alert, range_note.current());
        }
        if (fd >= 0) send_line(fd, box_line(primary));

        std::optional<Alert> stable = debounce.update(alert);
        if (!stable) continue;
        std::printf("  -> send %d %s\n", stable->level, stable->direction.c_str());
        if (fd < 0) continue;
        send_line(fd, std::to_string(stable->level) + " " + stable->direction + "\n");
    }
}
