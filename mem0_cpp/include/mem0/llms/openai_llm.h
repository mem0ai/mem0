#pragma once
#include "mem0/llms/llm_base.h"
#include "mem0/configs/llm_config.h" // Already included by llm_base.h but good for clarity
#include <string>
#include <vector>
#include <map>
#include <optional>
#include <any>
#include "nlohmann/json.hpp"
#include "httplib.h"

namespace mem0::llms {

    class OpenAILLM : public LLMBase {
    public:
        explicit OpenAILLM(const configs::BaseLlmConfig& config);
        ~OpenAILLM() override = default;

        LLMResponse generate_response(
            const std::vector<std::map<std::string, std::string>>& messages,
            const std::optional<std::string>& response_format_type = std::nullopt,
            const std::optional<std::vector<std::map<std::string, std::any>>>& tools = std::nullopt,
            const std::string& tool_choice = "auto"
        ) override;

    private:
        std::string api_key_;
        std::string model_name_;
        std::string base_url_;
        std::string api_path_ = "/v1/chat/completions";
        
        // For OpenRouter specific fields from config
        std::optional<std::vector<std::string>> openrouter_models_;
        std::optional<std::string> openrouter_route_;
        std::optional<std::string> openrouter_site_url_;
        std::optional<std::string> openrouter_app_name_;
        bool use_openrouter_ = false;


        LLMResponse parse_openai_response(const httplib::Result& res, bool has_tools);
    };

} // namespace mem0::llms
