#pragma once
#include <string>
#include <optional>
#include <map> // Not strictly needed for this simplified version

namespace mem0::configs {
    struct BaseVectorStoreConfig {
        std::optional<std::string> provider; 
        std::string collection_name = "mem0";
        std::optional<int> embedding_dims; 
        
        std::optional<std::string> chroma_path; 
        std::optional<std::string> chroma_host;
        std::optional<int> chroma_port;
        // Add other common fields or provider-specific config structs as needed
    };

    struct ChromaDetailConfig { // Example if needed for more detail
        std::string collection_name = "mem0";
        std::optional<std::string> path; 
        std::optional<std::string> host;
        std::optional<int> port;
    };
}
