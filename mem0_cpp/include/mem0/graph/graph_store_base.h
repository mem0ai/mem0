#pragma once
#include <string>
#include <vector>
#include <map>
#include <optional>
#include <any>
#include "../configs/graph_config.h"

namespace mem0::graph {
   // namespace configs { struct BaseGraphStoreConfig; }

    struct GraphEntity {
        std::string source;
        std::string relationship;
        std::string destination;
        std::optional<std::string> source_type;
        std::optional<std::string> destination_type;
    };
    
    struct GraphAddResult {
         std::vector<GraphEntity> added_entities;
         std::vector<GraphEntity> deleted_entities; // Or just a status
    };

    class GraphStoreBase {
    public:
        explicit GraphStoreBase(const configs::BaseGraphStoreConfig& config) : config_(config) {}
        virtual ~GraphStoreBase() = default;

        virtual GraphAddResult add(const std::string& data, const std::map<std::string, std::any>& filters) = 0;
        virtual std::vector<GraphEntity> search(const std::string& query, const std::map<std::string, std::any>& filters, int limit = 100) = 0;
        virtual void delete_all_user_data(const std::map<std::string, std::any>& filters) = 0; // e.g. based on user_id
        virtual std::vector<GraphEntity> get_all(const std::map<std::string, std::any>& filters, int limit = 100) = 0;
        // Potentially more granular methods like add_node, add_relationship, delete_relationship
    
    protected:
        configs::BaseGraphStoreConfig config_;
    };
}
