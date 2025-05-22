#pragma once
#include <string>
#include <vector>
#include <map>
#include <optional>
#include <any>
#include "../configs/memory_config.h" 

namespace mem0::memory {
   // namespace configs { struct MemoryConfig; struct MemoryItem; }

    struct AddResult {
        std::vector<configs::MemoryItem> results;
        std::optional<std::map<std::string, std::any>> relations; // Simplified for now
    };

    class MemoryBase {
    public:
        explicit MemoryBase(const configs::MemoryConfig& config) : config_(config) {}
        virtual ~MemoryBase() = default;

        virtual AddResult add(
            const std::vector<std::map<std::string, std::string>>& messages,
            const std::optional<std::string>& user_id = std::nullopt,
            const std::optional<std::string>& agent_id = std::nullopt,
            const std::optional<std::string>& run_id = std::nullopt,
            const std::optional<std::map<std::string, std::any>>& metadata = std::nullopt,
            bool infer = true,
            const std::optional<std::string>& memory_type = std::nullopt,
            const std::optional<std::string>& prompt = std::nullopt
        ) = 0;

        virtual std::optional<configs::MemoryItem> get(const std::string& memory_id) = 0;
        
        virtual AddResult get_all( // Reusing AddResult for structure, though 'relations' might be empty
            const std::optional<std::string>& user_id = std::nullopt,
            const std::optional<std::string>& agent_id = std::nullopt,
            const std::optional<std::string>& run_id = std::nullopt,
            const std::optional<std::map<std::string, std::any>>& filters = std::nullopt,
            int limit = 100
        ) = 0;

        virtual AddResult search(
            const std::string& query,
            const std::optional<std::string>& user_id = std::nullopt,
            const std::optional<std::string>& agent_id = std::nullopt,
            const std::optional<std::string>& run_id = std::nullopt,
            int limit = 100,
            const std::optional<std::map<std::string, std::any>>& filters = std::nullopt
        ) = 0;

        virtual std::string update(const std::string& memory_id, const std::string& data) = 0; // Returns a status message
        virtual std::string delete_memory(const std::string& memory_id) = 0; // Returns a status message
        
        virtual std::string delete_all(
            const std::optional<std::string>& user_id = std::nullopt,
            const std::optional<std::string>& agent_id = std::nullopt,
            const std::optional<std::string>& run_id = std::nullopt
        ) = 0; // Returns a status message

        // HistoryItem can be defined here or in a separate types.h
        struct HistoryItem {
            std::string memory_id;
            std::optional<std::string> prev_value;
            std::optional<std::string> new_value;
            std::string event_type; // ADD, UPDATE, DELETE
            std::string timestamp;
            std::optional<std::string> actor_id;
            std::optional<std::string> role;
            bool is_deleted = false;
        };
        virtual std::vector<HistoryItem> history(const std::string& memory_id) = 0;
        
        virtual void reset() = 0;

    protected:
        configs::MemoryConfig config_;
    };
}
