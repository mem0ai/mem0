#pragma once
#include <string>
#include <vector>
#include <map>
#include <optional>
#include <any> // For payload
#include "../configs/vector_store_config.h"

namespace mem0::vector_stores {
    // namespace configs { struct BaseVectorStoreConfig; }

    struct VectorStoreSearchResult {
        std::string id;
        double score = 0.0;
        std::map<std::string, std::any> payload;
        std::vector<float> vector; // Optional, depending on if needed by caller
    };
    
    struct VectorStoreData {
        std::string id;
        std::map<std::string, std::any> payload;
        std::vector<float> vector;
    };


    class VectorStoreBase {
    public:
        explicit VectorStoreBase(const configs::BaseVectorStoreConfig& config) : config_(config) {}
        virtual ~VectorStoreBase() = default;

        virtual void create_collection(const std::string& name, int vector_size, const std::string& distance_metric) = 0;
        virtual void insert(const std::vector<std::vector<float>>& vectors, const std::vector<std::map<std::string, std::any>>& payloads, const std::vector<std::string>& ids) = 0;
        virtual std::vector<VectorStoreSearchResult> search(const std::string& query, const std::vector<float>& vector, int limit = 5, const std::optional<std::map<std::string, std::any>>& filters = std::nullopt) = 0;
        virtual void delete_vector(const std::string& vector_id) = 0;
        virtual void update_vector(const std::string& vector_id, const std::optional<std::vector<float>>& vector = std::nullopt, const std::optional<std::map<std::string, std::any>>& payload = std::nullopt) = 0;
        virtual std::optional<VectorStoreData> get_vector(const std::string& vector_id) = 0;
        
        virtual std::vector<std::string> list_collections() = 0;
        virtual void delete_collection(const std::string& name) = 0;
        // virtual std::map<std::string, std::any> collection_info(const std::string& name) = 0; // Exact return type might vary
        
        virtual std::vector<VectorStoreData> list_vectors(const std::optional<std::map<std::string, std::any>>& filters = std::nullopt, std::optional<int> limit = std::nullopt) = 0;
        virtual void reset_collection() = 0; // Resets the configured collection

    protected:
        configs::BaseVectorStoreConfig config_;
    };
}
