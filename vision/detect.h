// DEIMv2 ONNX detector via onnxruntime (CPU). Port of PR #3's vision/detect.py.
#pragma once
#include "types.h"

#include <onnxruntime/onnxruntime_cxx_api.h>

class Detector {
public:
    Detector(const char* model_path, int threads);
    std::vector<Box> detect(const Frame& frame);

private:
    Ort::Env env_;
    Ort::Session session_;
    int64_t in_h_, in_w_;
    std::vector<float> images_;
};
