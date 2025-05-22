#pragma once
#include <string>
#include <vector>
#include <optional>
#include "../configs/embedder_config.h" // Relative path to config

namespace mem0::embeddings {
    // Forward declaration if BaseEmbedderConfig is in a different namespace and fully defined elsewhere
    // namespace configs { struct BaseEmbedderConfig; }

    class EmbeddingBase {
    public:
        explicit EmbeddingBase(const configs::BaseEmbedderConfig& config) : config_(config) {}
        virtual ~EmbeddingBase() = default;

        virtual std::vector<float> embed(const std::string& text, const std::optional<std::string>& memory_action = std::nullopt) = 0;

    protected:
        configs::BaseEmbedderConfig config_;
    };
}
