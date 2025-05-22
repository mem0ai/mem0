#include "mem0/embeddings/openai_embedding.h"
#include <iostream> // For potential logging/debugging
#include <stdexcept> // For exceptions
#include <cstdlib>   // For std::getenv

namespace mem0::embeddings {

    OpenAIEmbedding::OpenAIEmbedding(const configs::BaseEmbedderConfig& config)
        : EmbeddingBase(config) {
        
        api_key_ = config.api_key.value_or("");
        if (api_key_.empty()) {
            const char* env_api_key = std::getenv("OPENAI_API_KEY");
            if (env_api_key) {
                api_key_ = env_api_key;
            }
        }
        if (api_key_.empty()) {
            throw std::runtime_error("OpenAI API key is not provided in config or OPENAI_API_KEY environment variable.");
        }

        model_name_ = config.model.value_or("text-embedding-3-small");
        dimensions_ = config.embedding_dims; // std::optional<int>

        base_url_ = config.openai_base_url.value_or("api.openai.com");
        // Remove "https://" or "http://" from base_url_ if present, as httplib handles scheme separately or expects just hostname
        if (base_url_.rfind("https://", 0) == 0) {
            base_url_ = base_url_.substr(8);
        } else if (base_url_.rfind("http://", 0) == 0) {
            base_url_ = base_url_.substr(7);
        }
    }

    std::vector<float> OpenAIEmbedding::embed(
        const std::string& text,
        const std::optional<std::string>& memory_action) {
        
        // httplib::Client cli(base_url_.c_str()); // SSL client if base_url_ is for https
        // For "api.openai.com", SSL is required.
        httplib::SSLClient cli(base_url_.c_str());
        cli.set_default_headers({
            {"Authorization", "Bearer " + api_key_},
            {"Content-Type", "application/json"}
        });

        nlohmann::json body;
        body["input"] = text;
        body["model"] = model_name_;
        if (dimensions_.has_value()) {
            body["dimensions"] = dimensions_.value();
        }

        std::string body_str = body.dump();

        auto res = cli.Post(api_path_.c_str(), body_str, "application/json");

        if (!res) {
            auto err = res.error();
            throw std::runtime_error("HTTP request failed: " + httplib::to_string(err));
        }

        if (res->status != 200) {
            throw std::runtime_error("OpenAI API request failed with status " + std::to_string(res->status) + ": " + res->body);
        }

        try {
            nlohmann::json response_json = nlohmann::json::parse(res->body);
            if (response_json.contains("data") && response_json["data"].is_array() && !response_json["data"].empty()) {
                if (response_json["data"][0].contains("embedding") && response_json["data"][0]["embedding"].is_array()) {
                    return response_json["data"][0]["embedding"].get<std::vector<float>>();
                }
            }
            throw std::runtime_error("Invalid JSON response structure from OpenAI API.");
        } catch (const nlohmann::json::parse_error& e) {
            throw std::runtime_error("Failed to parse JSON response from OpenAI API: " + std::string(e.what()));
        }
    }

} // namespace mem0::embeddings
