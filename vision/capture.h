// Camera capture via the QNX camera API (sensor service). Frames arrive on the
// camera's thread; next() returns the newest one, dropping any we were too slow for.
#pragma once
#include "types.h"

#include <camera/camera_api.h>

#include <condition_variable>
#include <mutex>

class Capture {
public:
    explicit Capture(camera_unit_t unit);
    ~Capture();
    Frame next();  // blocks until a frame newer than the last one returned

private:
    static void on_frame(camera_handle_t, camera_buffer_t* buf, void* arg);

    camera_handle_t cam_ = CAMERA_HANDLE_INVALID;
    std::mutex mu_;
    std::condition_variable cv_;
    Frame latest_{};
    uint64_t seq_ = 0, taken_ = 0;
};
