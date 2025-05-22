#pragma once
#include <string>
#include <vector>
#include <map>
#include <optional>
#include "azure_config.h"

namespace mem0::configs {
    struct BaseLlmConfig {
        std::optional<std::string> model; 
        double temperature = 0.1;
        std::optional<std::string> api_key;
        int max_tokens = 2000;
        double top_p = 0.1;
        int top_k = 1; 
        bool enable_vision = false;
        std::optional<std::string> vision_details = "auto";
        std::optional<std::vector<std::string>> models; 
        std::optional<std::string> route = "fallback"; 
        std::optional<std::string> openrouter_base_url;
        std::optional<std::string> openai_base_url;
        std::optional<std::string> site_url; 
        std::optional<std::string> app_name; 
        std::optional<std::string> ollama_base_url;
        std::optional<AzureConfig> azure_kwargs;
        std::optional<std::map<std::string, std::string>> http_client_proxies; 
        std::optional<std::string> deepseek_base_url;
        std::optional<std::string> xai_base_url;
        std::optional<std::string> lmstudio_base_url = "http://localhost:1234/v1";
        std::optional<std::string> aws_access_key_id;
        std::optional<std::string> aws_secret_access_key;
        std::optional<std::string> aws_region = "us-west-2";
    };
}
