#pragma once
#include "mem0/vector_stores/vector_store_base.h"
#include "mem0/configs/vector_store_config.h" // Included by base, but good for clarity
#include <string>
#include <vector>
#include <map>
#include <optional>
#include <any>
#include "nlohmann/json.hpp"
#include "httplib.h"

namespace mem0::vector_stores {

    class ChromaVectorStore : public VectorStoreBase {
    public:
        explicit ChromaVectorStore(const configs::BaseVectorStoreConfig& config);
        ~ChromaVectorStore() override = default;

        void create_collection(const std::string& name, int vector_size, const std::string& distance_metric) override;
        void insert(const std::vector<std::vector<float>>& vectors, const std::vector<std::map<std::string, std::any>>& payloads, const std::vector<std::string>& ids) override;
        std::vector<VectorStoreSearchResult> search(const std::string& query_text, const std::vector<float>& vector, int limit = 5, const std::optional<std::map<std::string, std::any>>& filters = std::nullopt) override;
        void delete_vector(const std::string& vector_id) override;
        void update_vector(const std::string& vector_id, const std::optional<std::vector<float>>& vector = std::nullopt, const std::optional<std::map<std::string, std::any>>& payload = std::nullopt) override;
        std::optional<VectorStoreData> get_vector(const std::string& vector_id) override;
        
        std::vector<std::string> list_collections() override;
        void delete_collection(const std::string& name) override;
        // std::map<std::string, std::any> collection_info(const std::string& name) override; // Implement if API endpoint exists
        
        std::vector<VectorStoreData> list_vectors(const std::optional<std::map<std::string, std::any>>& filters = std::nullopt, std::optional<int> limit = std::nullopt) override;
        void reset_collection() override;

    private:
        std::string host_;
        int port_;
        std::string collection_name_; // From config_
        std::optional<int> embedding_dims_; // From config_

        // Helper to make requests
        httplib::Result make_request(
            const std::string& method, 
            const std::string& path, 
            const nlohmann::json& body = nlohmann::json(), // Default to empty json object
            const httplib::Headers& headers = {});
        
        // Helper to parse std::any for metadata serialization
        nlohmann::json any_to_json(const std::any& val);
        std::map<std::string, nlohmann::json> serialize_payload(const std::map<std::string, std::any>& payload);
        std::map<std::string, std::any> deserialize_payload(const nlohmann::json& json_payload);
    };

} // namespace mem0::vector_stores
