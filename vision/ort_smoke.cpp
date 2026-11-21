// onnxruntime smoke test: load a model, feed zero-filled inputs, time 20 runs.
// Usage: ./ort_smoke model.onnx [shape of input 0, e.g. 1,3,416,416] [intra-op threads]
// Dynamic dims (-1) are set to 1. Only float and int64 inputs are supported.
// Pass "" to use the shapes the model declares.

#include <onnxruntime/onnxruntime_cxx_api.h>

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

int main(int argc, char** argv) {
    if (argc < 2 || argc > 4) { std::fprintf(stderr, "usage: %s model.onnx [1,3,416,416] [threads]\n", argv[0]); return 1; }
    std::vector<int64_t> shape_override;
    if (argc >= 3) {
        for (char* p = argv[2]; *p != '\0';) {
            shape_override.push_back(std::strtoll(p, &p, 10));
            if (*p == ',') ++p;
        }
    }

    Ort::Env env(ORT_LOGGING_LEVEL_WARNING, "ort_smoke");
    Ort::SessionOptions opts;
    if (argc == 4) {
        opts.SetIntraOpNumThreads(std::atoi(argv[3]));
        std::printf("intra-op threads: %s\n", argv[3]);
    }
    Ort::Session session(env, argv[1], opts);
    Ort::AllocatorWithDefaultOptions alloc;
    auto mem = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);

    std::vector<std::string> in_names, out_names;
    std::vector<std::vector<float>> f_bufs;
    std::vector<std::vector<int64_t>> i_bufs;
    std::vector<Ort::Value> inputs;

    for (size_t i = 0; i < session.GetInputCount(); ++i) {
        in_names.push_back(session.GetInputNameAllocated(i, alloc).get());
        Ort::TypeInfo type_info = session.GetInputTypeInfo(i);  // must outlive `info`, which points into it
        auto info = type_info.GetTensorTypeAndShapeInfo();
        auto shape = (i == 0 && !shape_override.empty()) ? shape_override : info.GetShape();
        size_t n = 1;
        for (auto& d : shape) { if (d < 0) d = 1; n *= static_cast<size_t>(d); }

        std::printf("input %s [", in_names.back().c_str());
        for (auto d : shape) std::printf(" %lld", static_cast<long long>(d));
        std::printf(" ] type %d\n", static_cast<int>(info.GetElementType()));

        switch (info.GetElementType()) {
        case ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT:
            f_bufs.emplace_back(n, 0.0f);
            inputs.push_back(Ort::Value::CreateTensor<float>(mem, f_bufs.back().data(), n, shape.data(), shape.size()));
            break;
        case ONNX_TENSOR_ELEMENT_DATA_TYPE_INT64:
            i_bufs.emplace_back(n, 640);  // e.g. orig_target_sizes for DEIMv2
            inputs.push_back(Ort::Value::CreateTensor<int64_t>(mem, i_bufs.back().data(), n, shape.data(), shape.size()));
            break;
        default:
            std::fprintf(stderr, "unsupported input type %d\n", static_cast<int>(info.GetElementType()));
            return 1;
        }
    }
    for (size_t i = 0; i < session.GetOutputCount(); ++i)
        out_names.push_back(session.GetOutputNameAllocated(i, alloc).get());

    std::vector<const char*> in_c, out_c;
    for (auto& s : in_names) in_c.push_back(s.c_str());
    for (auto& s : out_names) out_c.push_back(s.c_str());

    for (int run = 0; run < 20; ++run) {
        auto t0 = std::chrono::steady_clock::now();
        auto outs = session.Run(Ort::RunOptions{nullptr}, in_c.data(), inputs.data(), inputs.size(), out_c.data(), out_c.size());
        auto ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
        std::printf("run %2d: %.1f ms\n", run, ms);
        if (run == 0) {
            for (size_t i = 0; i < outs.size(); ++i) {
                auto shape = outs[i].GetTensorTypeAndShapeInfo().GetShape();
                std::printf("output %s [", out_names[i].c_str());
                for (auto d : shape) std::printf(" %lld", static_cast<long long>(d));
                std::printf(" ]\n");
            }
        }
    }
    return 0;
}
