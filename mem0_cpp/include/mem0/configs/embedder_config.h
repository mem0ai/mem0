#pragma once
#include <string>
#include <vector> 
#include <map>
#include <optional>
#include "azure_config.h"

namespace mem0::configs {
    struct BaseEmbedderConfig {
        std::optional<std::string> model;
        std::optional<std::string> api_key;
        std::optional<int> embedding_dims;
        std::optional<std::string> ollama_base_url;
        std::optional<std::string> openai_base_url;
        std::optional<std::map<std::string, std::string>> model_kwargs; 
        std::optional<std::string> huggingface_base_url;
        std::optional<AzureConfig> azure_kwargs;
        std::optional<std::map<std::string, std::string>> http_client_proxies; 
        std::optional<std::string> vertex_credentials_json;
        std::optional<std::string> memory_add_embedding_type;
        std::optional<std::string> memory_update_embedding_type;
        std::optional<std::string> memory_search_embedding_type;
        std::optional<std::string> lmstudio_base_url = "http://localhost:1234/v1";
        std::optional<std::string> aws_access_key_id;
        std::optional<std::string> aws_secret_access_key;
        std::optional<std::string> aws_region = "us-west-2";
    };
}
