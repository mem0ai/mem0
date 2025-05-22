#pragma once
#include <string>
#include <optional>
#include <vector> 
#include <map>    
#include <any>    
#include "vector_store_config.h"
#include "llm_config.h"
#include "embedder_config.h"
#include "graph_config.h"

namespace mem0::configs {
    struct MemoryItem { 
        std::string id;
        std::string memory;
        std::optional<std::string> hash;
        std::optional<std::map<std::string, std::any>> metadata; 
        std::optional<double> score;
        std::optional<std::string> created_at;
        std::optional<std::string> updated_at;
    };
    
    struct MemoryConfig {
        BaseVectorStoreConfig vector_store;
        BaseLlmConfig llm;
        BaseEmbedderConfig embedder;
        std::string history_db_path = ".mem0/history.db"; 
        std::optional<BaseGraphStoreConfig> graph_store;
        std::string version = "v1.1";
        std::optional<std::string> custom_fact_extraction_prompt;
        std::optional<std::string> custom_update_memory_prompt;
    };
}
