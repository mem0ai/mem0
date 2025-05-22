#pragma once
#include <string>
#include <optional>
#include "llm_config.h" 

namespace mem0::configs {
    struct BaseGraphStoreConfig {
        std::optional<std::string> provider; 
        
        std::optional<std::string> neo4j_url;
        std::optional<std::string> neo4j_username;
        std::optional<std::string> neo4j_password;
        std::optional<std::string> neo4j_database;
        bool neo4j_refresh_schema = false; 
        std::optional<std::string> neo4j_base_label = "__Entity__"; 

        std::optional<BaseLlmConfig> llm_config; 
        std::optional<std::string> custom_prompt;
    };
}
