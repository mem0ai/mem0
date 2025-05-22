#include <iostream>
#include <vector>
#include <string>
#include <optional>
#include <cstdlib> // For std::getenv
#include <map>
#include <any>
#include <stdexcept> // For std::runtime_error

#include "httplib.h" 
#include "nlohmann/json.hpp" 

// Mem0 project headers
#include "mem0/configs/memory_config.h" 
#include "mem0/configs/embedder_config.h"
#include "mem0/embeddings/openai_embedding.h"
#include "mem0/configs/llm_config.h"
#include "mem0/llms/openai_llm.h"
#include "mem0/configs/vector_store_config.h"
#include "mem0/vector_stores/chroma_vector_store.h" // Include the new header

// Helper function to print LLMResponse (from previous subtask)
void print_llm_response(const mem0::llms::LLMResponse& response) {
    if (response.content.has_value()) {
        std::cout << "LLM Content: " << response.content.value() << std::endl;
    } else {
        std::cout << "LLM Content: [None]" << std::endl;
    }

    if (!response.tool_calls.empty()) {
        std::cout << "Tool Calls (" << response.tool_calls.size() << "):" << std::endl;
        for (size_t i = 0; i < response.tool_calls.size(); ++i) {
            const auto& tc = response.tool_calls[i];
            std::cout << "  Tool Call " << i + 1 << ":" << std::endl;
            std::cout << "    Name: " << tc.name << std::endl;
            std::cout << "    Arguments: {" << std::endl;
            for (const auto& arg_pair : tc.arguments) {
                std::cout << "      \"" << arg_pair.first << "\": ";
                try {
                    if (arg_pair.second.type() == typeid(std::string)) {
                        std::cout << "\"" << std::any_cast<std::string>(arg_pair.second) << "\"";
                    } else if (arg_pair.second.type() == typeid(int)) {
                        std::cout << std::any_cast<int>(arg_pair.second);
                    } else if (arg_pair.second.type() == typeid(double)) {
                        std::cout << std::any_cast<double>(arg_pair.second);
                    } else if (arg_pair.second.type() == typeid(bool)) {
                        std::cout << (std::any_cast<bool>(arg_pair.second) ? "true" : "false");
                    } else if (arg_pair.second.type() == typeid(nlohmann::json)) {
                        std::cout << std::any_cast<nlohmann::json>(arg_pair.second).dump();
                    }
                     else {
                        std::cout << "[unsupported type: " << arg_pair.second.type().name() << "]";
                    }
                } catch (const std::bad_any_cast& e) {
                    std::cout << "[bad_any_cast: " << e.what() << "]";
                }
                std::cout << std::endl;
            }
            std::cout << "    }" << std::endl;
        }
    } else {
        std::cout << "Tool Calls: [None]" << std::endl;
    }
}

// Helper to print VectorStoreSearchResult
void print_search_result(const mem0::vector_stores::VectorStoreSearchResult& result) {
    std::cout << "  ID: " << result.id << ", Score: " << result.score << std::endl;
    std::cout << "  Payload: {" << std::endl;
    for (const auto& pair : result.payload) {
        std::cout << "    \"" << pair.first << "\": ";
        // Basic printing for std::any, extend as needed
        if (pair.second.type() == typeid(std::string)) {
            std::cout << "\"" << std::any_cast<std::string>(pair.second) << "\"";
        } else if (pair.second.type() == typeid(int)) {
            std::cout << std::any_cast<int>(pair.second);
        } else if (pair.second.type() == typeid(double)) {
            std::cout << std::any_cast<double>(pair.second);
        } else {
            std::cout << "[type: " << pair.second.type().name() << "]";
        }
        std::cout << std::endl;
    }
    std::cout << "  }" << std::endl;
}

int main() {
    std::cout << "--- Mem0 C++ Test App ---" << std::endl;

    // Test OpenAIEmbedding (can be commented out)
    // ... (previous OpenAIEmbedding test code) ...

    // Test OpenAILLM (can be commented out)
    // ... (previous OpenAILLM test code) ...

    // Test ChromaVectorStore
    std::cout << "\n--- Testing ChromaVectorStore ---" << std::endl;
    try {
        mem0::configs::BaseVectorStoreConfig chroma_config;
        chroma_config.provider = "chroma"; // Informational
        chroma_config.collection_name = "mem0_cpp_test_collection";
        // chroma_config.chroma_host = "localhost"; // Default in struct
        // chroma_config.chroma_port = 8000;       // Default in struct
        // chroma_config.embedding_dims = 1536; // Set if your Chroma instance requires it for new collections
                                              // and if OpenAIEmbedding (default) is used.

        std::cout << "Attempting to connect to ChromaDB at "
                  << chroma_config.chroma_host.value_or("N/A") << ":"
                  << chroma_config.chroma_port.value_or(0)
                  << " for collection: " << chroma_config.collection_name
                  << std::endl;
        
        mem0::vector_stores::ChromaVectorStore chroma_vs(chroma_config);
        std::cout << "ChromaVectorStore instantiated. Collection should be created or verified." << std::endl;

        // Prepare some data
        std::string id1 = "vec1";
        std::vector<float> vec1 = {0.1f, 0.2f, 0.3f}; // Ensure dimension matches OpenAI or other embedder
        std::map<std::string, std::any> payload1 = {{"source", std::string("doc1.txt")}, {"page", 1}};

        std::string id2 = "vec2";
        std::vector<float> vec2 = {0.4f, 0.5f, 0.6f};
        std::map<std::string, std::any> payload2 = {{"source", std::string("doc2.txt")}, {"page", 5}};
        
        // For this test, we will use placeholder embeddings.
        // A real test would use an actual embedder.
        // If your Chroma requires specific dimension, ensure these vectors match.
        // The OpenAI default (text-embedding-3-small) is 1536.
        // If embedding_dims was not set in chroma_config for collection creation, this might be an issue.
        // For a simple HTTP test, Chroma might not validate dimensions as strictly as a typed client.

        std::cout << "\nInserting vectors..." << std::endl;
        chroma_vs.insert({vec1, vec2}, {payload1, payload2}, {id1, id2});
        std::cout << "Vectors inserted." << std::endl;

        std::cout << "\nSearching for vector similar to vec1..." << std::endl;
        std::vector<mem0::vector_stores::VectorStoreSearchResult> search_results = chroma_vs.search("query text (not used by this HTTP search)", vec1, 2);
        std::cout << "Search results (" << search_results.size() << "):" << std::endl;
        for (const auto& res : search_results) {
            print_search_result(res);
        }
        
        std::cout << "\nGetting vector by ID: " << id1 << std::endl;
        std::optional<mem0::vector_stores::VectorStoreData> got_vec_data = chroma_vs.get_vector(id1);
        if (got_vec_data.has_value()) {
            std::cout << "Got vector: " << got_vec_data->id << ", Payload keys: " << got_vec_data->payload.size() << std::endl;
        } else {
            std::cout << "Vector " << id1 << " not found." << std::endl;
        }

        std::cout << "\nListing all vectors in collection (limit 5):" << std::endl;
        std::vector<mem0::vector_stores::VectorStoreData> all_vectors = chroma_vs.list_vectors(std::nullopt, 5);
         std::cout << "Found " << all_vectors.size() << " vectors:" << std::endl;
        for(const auto& v_data : all_vectors){
            std::cout << "  ID: " << v_data.id << ", Payload keys: " << v_data.payload.size() << ", Vector dims: " << v_data.vector.size() << std::endl;
        }


        std::cout << "\nDeleting vector by ID: " << id1 << std::endl;
        chroma_vs.delete_vector(id1);
        std::cout << "Vector " << id1 << " deleted." << std::endl;
        
        std::optional<mem0::vector_stores::VectorStoreData> deleted_vec_check = chroma_vs.get_vector(id1);
        if (!deleted_vec_check.has_value()) {
            std::cout << "Vector " << id1 << " successfully confirmed deleted (not found)." << std::endl;
        } else {
            std::cout << "Error: Vector " << id1 << " still found after deletion." << std::endl;
        }

        // Clean up: Reset (delete and recreate) collection
        // std::cout << "\nResetting collection..." << std::endl;
        // chroma_vs.reset_collection();
        // std::cout << "Collection reset." << std::endl;


    } catch (const std::runtime_error& e) {
        std::cerr << "ChromaVectorStore Test Error: " << e.what() << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "An unexpected error occurred during ChromaVectorStore test: " << e.what() << std::endl;
    }


    std::cout << "\n--- Test App Finished ---" << std::endl;
    return 0;
}
