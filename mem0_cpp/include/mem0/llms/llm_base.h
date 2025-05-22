#pragma once
#include <string>
#include <vector>
#include <map>
#include <optional>
#include <any> // For tool call arguments
#include "../configs/llm_config.h" // Relative path to config

namespace mem0::llms {
    // Forward declaration
    // namespace configs { struct BaseLlmConfig; }

    // Define a structure for tool calls, similar to Python's dict structure
    struct ToolCall {
        std::string name;
        std::map<std::string, std::any> arguments;
    };
    
    struct LLMResponse {
        std::optional<std::string> content;
        std::vector<ToolCall> tool_calls;
    };

    class LLMBase {
    public:
        explicit LLMBase(const configs::BaseLlmConfig& config) : config_(config) {}
        virtual ~LLMBase() = default;

        virtual LLMResponse generate_response(
            const std::vector<std::map<std::string, std::string>>& messages,
            const std::optional<std::string>& response_format_type = std::nullopt, // e.g., "json_object"
            const std::optional<std::vector<std::map<std::string, std::any>>>& tools = std::nullopt,
            const std::string& tool_choice = "auto"
        ) = 0;

    protected:
        configs::BaseLlmConfig config_;
    };
}
