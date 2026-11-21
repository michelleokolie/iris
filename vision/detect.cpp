#include "detect.h"

#include <algorithm>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <string>

// Default 0.4 (as PR #3); VISION_SCORE overrides it for tuning on the board.
static const float SCORE_THRESHOLD = std::getenv("VISION_SCORE") ? std::strtof(std::getenv("VISION_SCORE"), nullptr) : 0.4f;

static Ort::SessionOptions options(int threads) {
    Ort::SessionOptions opts;
    opts.SetIntraOpNumThreads(threads);
    return opts;
}

Detector::Detector(const char* model_path, int threads)
    : env_(ORT_LOGGING_LEVEL_WARNING, "vision"), session_(env_, model_path, options(threads)) {
    Ort::TypeInfo images_info = session_.GetInputTypeInfo(0);
    auto shape = images_info.GetTensorTypeAndShapeInfo().GetShape();  // [1, 3, H, W]
    in_h_ = shape[2];
    in_w_ = shape[3];
    images_.resize(static_cast<size_t>(3 * in_h_ * in_w_));

    Ort::TypeInfo labels_info = session_.GetOutputTypeInfo(0);
    if (labels_info.GetTensorTypeAndShapeInfo().GetElementType() != ONNX_TENSOR_ELEMENT_DATA_TYPE_INT64) {
        std::fprintf(stderr, "expected int64 labels as output 0\n");
        std::exit(1);
    }
}

std::vector<Box> Detector::detect(const Frame& frame) {
    // Nearest-neighbour resize, BGR -> RGB, /255, HWC -> CHW.
    const size_t plane = static_cast<size_t>(in_h_ * in_w_);
    for (int64_t y = 0; y < in_h_; ++y) {
        int sy = static_cast<int>(y * frame.height / in_h_);
        for (int64_t x = 0; x < in_w_; ++x) {
            int sx = static_cast<int>(x * frame.width / in_w_);
            const uint8_t* px = &frame.bgr[(static_cast<size_t>(sy) * frame.width + sx) * 3];
            size_t i = static_cast<size_t>(y * in_w_ + x);
            images_[i] = px[2] / 255.0f;
            images_[plane + i] = px[1] / 255.0f;
            images_[2 * plane + i] = px[0] / 255.0f;
        }
    }

    auto mem = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
    std::array<int64_t, 4> images_shape{1, 3, in_h_, in_w_};
    std::array<int64_t, 2> sizes{frame.width, frame.height};  // DEIM wants [w, h]; boxes come back scaled by it
    std::array<int64_t, 2> sizes_shape{1, 2};
    std::array<Ort::Value, 2> inputs{
        Ort::Value::CreateTensor<float>(mem, images_.data(), images_.size(), images_shape.data(), images_shape.size()),
        Ort::Value::CreateTensor<int64_t>(mem, sizes.data(), sizes.size(), sizes_shape.data(), sizes_shape.size()),
    };
    const char* in_names[] = {"images", "orig_target_sizes"};
    const char* out_names[] = {"labels", "boxes", "scores"};
    auto outs = session_.Run(Ort::RunOptions{nullptr}, in_names, inputs.data(), inputs.size(), out_names, 3);

    const int64_t* labels = outs[0].GetTensorData<int64_t>();
    const float* boxes = outs[1].GetTensorData<float>();  // x1, y1, x2, y2 in frame pixels
    const float* scores = outs[2].GetTensorData<float>();
    size_t n = static_cast<size_t>(outs[2].GetTensorTypeAndShapeInfo().GetShape()[1]);

    std::vector<Box> out;
    for (size_t i = 0; i < n; ++i) {
        if (scores[i] < SCORE_THRESHOLD) continue;
        const float* b = &boxes[i * 4];
        // The model can return boxes a hair outside the frame (seen: x1 = -0.004); clip to it.
        auto unit = [](float v) { return std::clamp(v, 0.0f, 1.0f); };
        Box box{unit(b[0] / frame.width), unit(b[1] / frame.height), unit(b[2] / frame.width),
                unit(b[3] / frame.height), std::to_string(labels[i]), scores[i]};
        if (box.x2 <= box.x1 || box.y2 <= box.y1) continue;  // nothing of it is inside the frame
        out.push_back(box);
    }
    return out;
}
