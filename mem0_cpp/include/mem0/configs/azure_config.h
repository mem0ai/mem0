#pragma once
#include <string>
#include <vector> // Not strictly needed for this file but often included
#include <map>
#include <optional>

namespace mem0::configs {
    struct AzureConfig {
        std::optional<std::string> api_key;
        std::optional<std::string> azure_deployment;
        std::optional<std::string> azure_endpoint;
        std::optional<std::string> api_version;
        std::optional<std::map<std::string, std::string>> default_headers;
    };
}
