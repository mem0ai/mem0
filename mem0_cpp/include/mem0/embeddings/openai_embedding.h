#pragma once
#include "mem0/embeddings/embedding_base.h"
#include "mem0/configs/embedder_config.h" // Already included by embedding_base.h but good for clarity
#include <string>
#include <vector>
#include <optional>
#include "nlohmann/json.hpp" // For json parsing
#include "httplib.h"         // For HTTP client

namespace mem0::embeddings {

    class OpenAIEmbedding : public EmbeddingBase {
    public:
        explicit OpenAIEmbedding(const configs::BaseEmbedderConfig& config);
        ~OpenAIEmbedding() override = default;

        std::vector<float> embed(
            const std::string& text,
            const std::optional<std::string>& memory_action = std::nullopt
        ) override;

    private:
        std::string api_key_;
        std::string model_name_;
        std::optional<int> dimensions_;
        std::string base_url_;
        std::string api_path_ = "/v1/embeddings";

        // httplib client is not thread-safe for multiple requests on the same client instance
        // For simplicity now, we create it per request or ensure single-threaded access.
        // A more robust solution might involve a pool of clients or a thread-safe request mechanism.
    };

} // namespace mem0::embeddings
