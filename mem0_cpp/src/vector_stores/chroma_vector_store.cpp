#include "mem0/vector_stores/chroma_vector_store.h"
#include <stdexcept> // For exceptions
#include <iostream>  // For debugging

namespace mem0::vector_stores {

    // Helper to convert basic std::any types to nlohmann::json
    // Extend this as needed for more complex types stored in metadata.
    nlohmann::json ChromaVectorStore::any_to_json(const std::any& val) {
        if (!val.has_value()) return nlohmann::json(); // Handle empty std::any

        if (val.type() == typeid(std::string)) {
            return std::any_cast<std::string>(val);
        } else if (val.type() == typeid(int)) {
            return std::any_cast<int>(val);
        } else if (val.type() == typeid(long)) { // Added long
            return std::any_cast<long>(val);
        } else if (val.type() == typeid(long long)) { // Added long long
            return std::any_cast<long long>(val);
        } else if (val.type() == typeid(float)) { // Added float
            return std::any_cast<float>(val);
        } else if (val.type() == typeid(double)) {
            return std::any_cast<double>(val);
        } else if (val.type() == typeid(bool)) {
            return std::any_cast<bool>(val);
        } else if (val.type() == typeid(const char*)) {
            return std::string(std::any_cast<const char*>(val));
        }
        // Add more types as necessary, or serialize complex types to string/JSON string
        std::cerr << "Warning: Unsupported type in any_to_json: " << val.type().name() << std::endl;
        return nlohmann::json(); // Or throw error for unsupported type
    }

    std::map<std::string, nlohmann::json> ChromaVectorStore::serialize_payload(const std::map<std::string, std::any>& payload) {
        std::map<std::string, nlohmann::json> json_payload;
        for (const auto& pair : payload) {
            json_payload[pair.first] = any_to_json(pair.second);
        }
        return json_payload;
    }
    
    std::map<std::string, std::any> ChromaVectorStore::deserialize_payload(const nlohmann::json& json_payload) {
        std::map<std::string, std::any> payload;
        if (json_payload.is_object()) {
            for (auto it = json_payload.begin(); it != json_payload.end(); ++it) {
                if (it.value().is_string()) {
                    payload[it.key()] = it.value().get<std::string>();
                } else if (it.value().is_number_integer()) {
                    // Prefer larger type to avoid overflow, can be cast later if needed
                    payload[it.key()] = it.value().get<long long>(); 
                } else if (it.value().is_number_float()) {
                    payload[it.key()] = it.value().get<double>();
                } else if (it.value().is_boolean()) {
                    payload[it.key()] = it.value().get<bool>();
                } else if (it.value().is_null()){
                    // payload[it.key()] = nullptr; // std::any cannot hold nullptr directly in a useful way without type
                }
                // Add more types if needed (e.g. arrays, nested objects by converting them to vector<any> or map<string,any>)
            }
        }
        return payload;
    }


    ChromaVectorStore::ChromaVectorStore(const configs::BaseVectorStoreConfig& config)
        : VectorStoreBase(config) {
        host_ = config.chroma_host.value_or("localhost");
        port_ = config.chroma_port.value_or(8000);
        collection_name_ = config.collection_name; // Defaults to "mem0"
        embedding_dims_ = config.embedding_dims; 
        
        // Attempt to create the collection if it doesn't exist.
        // This is a "best effort" during construction. Robust applications might manage this externally.
        try {
            std::vector<std::string> collections = list_collections();
            bool found = false;
            for (const auto& col_name : collections) {
                if (col_name == collection_name_) {
                    found = true;
                    std::cout << "ChromaDB: Collection '" << collection_name_ << "' already exists." << std::endl;
                    break;
                }
            }
            if (!found) {
                 std::cout << "ChromaDB: Collection '" << collection_name_ << "' not found, attempting to create." << std::endl;
                // Defaulting distance to cosine as it's common. Chroma's default is L2.
                // The embedding_dims_ may or may not be required by the API for creation.
                // The Python client often infers or uses a default embedding function that sets this.
                // For direct HTTP, this might be part of 'metadata' in create collection body.
                std::string distance_metric = "cosine"; // Or "l2", "ip"
                create_collection(collection_name_, embedding_dims_.value_or(0), distance_metric);
            }
        } catch (const std::exception& e) {
            // Log the error but don't necessarily fail construction,
            // as the DB might be temporarily unavailable or collection creation might succeed later.
            std::cerr << "ChromaDB: Error during initial collection check/create for '" << collection_name_ 
                      << "': " << e.what() << ". The store might not function correctly." << std::endl;
        }
    }

    httplib::Result ChromaVectorStore::make_request(
        const std::string& method, 
        const std::string& path, 
        const nlohmann::json& body, // Default is nlohmann::json::object() which is not nullptr
        const httplib::Headers& headers_param) {
        
        httplib::Client cli(host_.c_str(), port_);
        cli.set_connection_timeout(10); // 10s
        cli.set_read_timeout(30);    // 30s
        cli.set_write_timeout(30);   // 30s

        httplib::Headers req_headers = { {"Content-Type", "application/json"} };
        for(const auto& h : headers_param) { // Add any additional headers
            req_headers.emplace(h.first, h.second);
        }
        // httplib::Result res; // Declare outside if-else
        if (method == "POST") {
            if (body.is_null()) { // Check if body is intentionally null (e.g. for some GET-like POSTs)
                 return cli.Post(path.c_str(), req_headers, "", "application/json"); // Empty body
            }
            return cli.Post(path.c_str(), req_headers, body.dump(), "application/json");
        } else if (method == "GET") {
            return cli.Get(path.c_str(), req_headers);
        } else if (method == "DELETE") {
            // Delete might have a body or not, depending on API. Chroma often uses body for DELETE.
            if (body.is_null()) {
                 return cli.Delete(path.c_str(), req_headers);
            }
            return cli.Delete(path.c_str(), req_headers, body.dump(), "application/json");
        }
        // Fallback for unsupported methods
        return httplib::Result(nullptr, httplib::Error::Unknown, httplib::Headers{});
    }

    void ChromaVectorStore::create_collection(const std::string& name, int vector_size, const std::string& distance_metric) {
        std::string api_path = "/api/v1/collections";
        nlohmann::json body = {
            {"name", name}
        };
        // Chroma's API for metadata (like distance function or dimensions) can be tricky.
        // It's often set via "metadata" field for the collection.
        // e.g., body["metadata"] = {{"hnsw:space", distance_metric}}; (for cosine, l2, ip)
        // If vector_size (embedding_dims) is needed at creation, it might also go into metadata.
        // Chroma's default is "l2". Let's explicitly set it if not "l2".
        if (distance_metric == "cosine" || distance_metric == "ip" || distance_metric == "l2") {
             body["metadata"] = {{"hnsw:space", distance_metric}};
        } else if (!distance_metric.empty() && distance_metric != "l2") { // Chroma's default
            std::cout << "ChromaDB: Warning - unsupported or unknown distance_metric '" << distance_metric 
                      << "' for hnsw:space. Using Chroma's default (L2)." << std::endl;
        }
        // If embedding_dims_ (vector_size) needs to be passed, it might be like:
        // if (vector_size > 0) body["metadata"]["dim"] = vector_size; // This is hypothetical, check Chroma API docs

        auto res = make_request("POST", api_path, body);
        // Successful creation is 201. 409 means it already exists.
        if (!res || (res->status != 201 && res->status != 409)) { 
            std::string err_msg = "ChromaDB: Failed to create collection '" + name + "'. ";
            if(res) err_msg += "Status: " + std::to_string(res->status) + ", Body: " + res->body;
            else err_msg += "Request Error: " + httplib::to_string(res.error());
            throw std::runtime_error(err_msg);
        }
        if (res->status == 409) {
             std::cout << "ChromaDB: Collection '" << name << "' already exists." << std::endl;
        } else {
             std::cout << "ChromaDB: Collection '" << name << "' created successfully." << std::endl;
        }
        collection_name_ = name; // Update active collection name
        if (embedding_dims_.has_value() && vector_size > 0 && embedding_dims_.value() != vector_size) {
             std::cout << "ChromaDB: Warning - collection created with dimension " << vector_size 
                       << " but config has " << embedding_dims_.value() << std::endl;
        }
        if (vector_size > 0) embedding_dims_ = vector_size; // Update if provided
    }

    void ChromaVectorStore::insert(const std::vector<std::vector<float>>& vectors, const std::vector<std::map<std::string, std::any>>& payloads, const std::vector<std::string>& ids) {
        if (vectors.empty() || ids.empty() || payloads.size() != vectors.size() || ids.size() != vectors.size()) {
            throw std::runtime_error("ChromaDB: Invalid arguments for insert. Vectors, IDs, and Payloads must be non-empty and of the same size.");
        }
        // Chroma's API path for adding embeddings is typically POST /api/v1/collections/{collection_name}/add
        std::string api_path = "/api/v1/collections/" + collection_name_ + "/add";
        
        nlohmann::json body;
        body["ids"] = ids;
        body["embeddings"] = vectors;
        std::vector<nlohmann::json> json_payloads;
        json_payloads.reserve(payloads.size());
        for(const auto& p : payloads) {
            json_payloads.push_back(serialize_payload(p));
        }
        body["metadatas"] = json_payloads;

        auto res = make_request("POST", api_path, body);
        // Chroma uses 201 for successful 'add'
        if (!res || res->status != 201) { 
             std::string err_msg = "ChromaDB: Failed to insert vectors into '" + collection_name_ + "'. ";
            if(res) err_msg += "Status: " + std::to_string(res->status) + ", Body: " + res->body;
            else err_msg += "Request Error: " + httplib::to_string(res.error());
            throw std::runtime_error(err_msg);
        }
    }

    std::vector<VectorStoreSearchResult> ChromaVectorStore::search(const std::string& query_text /*unused*/, const std::vector<float>& vector, int limit, const std::optional<std::map<std::string, std::any>>& filters) {
        std::string api_path = "/api/v1/collections/" + collection_name_ + "/query";
        nlohmann::json body = {
            {"query_embeddings", {vector}}, // Chroma expects a list of embeddings
            {"n_results", limit},
            {"include", {"metadatas", "distances", "embeddings"}} // Request embeddings too
        };
        if (filters.has_value() && !filters.value().empty()) {
            // Chroma's "where" filter can be complex.
            // Simple key-value: {"key": "value"}
            // More complex: {"$and": [{"key1": "val1"}, {"key2": {"$eq": "val2"}}]}
            // For now, assume serialize_payload produces a compatible simple structure.
            body["where"] = serialize_payload(filters.value()); 
        }
        
        auto res = make_request("POST", api_path, body);
        if (!res || res->status != 200) {
            std::string err_msg = "ChromaDB: Failed to search vectors in '" + collection_name_ + "'. ";
            if(res) err_msg += "Status: " + std::to_string(res->status) + ", Body: " + res->body;
            else err_msg += "Request Error: " + httplib::to_string(res.error());
            throw std::runtime_error(err_msg);
        }

        std::vector<VectorStoreSearchResult> results;
        try {
            nlohmann::json res_json = nlohmann::json::parse(res->body);
            // Chroma query response structure for a single query vector:
            // { "ids": [["id1", "id2"]], "distances": [[0.1, 0.2]], "metadatas": [[{...}, {...}]], "embeddings": [[[...],[...]]], "documents": [[null, null]] }
            if (res_json.contains("ids") && res_json["ids"].is_array() && !res_json["ids"].empty() &&
                res_json.contains("distances") && res_json["distances"].is_array() && !res_json["distances"].empty() &&
                res_json.contains("metadatas") && res_json["metadatas"].is_array() && !res_json["metadatas"].empty()) {

                const auto& ids_list_outer = res_json["ids"];
                const auto& dist_list_outer = res_json["distances"];
                const auto& meta_list_outer = res_json["metadatas"];
                const auto& emb_list_outer = (res_json.contains("embeddings") && !res_json["embeddings"].is_null() && res_json["embeddings"].is_array()) ? res_json["embeddings"] : nlohmann::json::array();

                if (!ids_list_outer.empty()){
                    const auto& ids_list = ids_list_outer[0];
                    const auto& dist_list = dist_list_outer[0];
                    const auto& meta_list = meta_list_outer[0];
                    const auto& emb_list = (!emb_list_outer.empty() && emb_list_outer[0].is_array()) ? emb_list_outer[0] : nlohmann::json::array();

                    for (size_t i = 0; i < ids_list.size(); ++i) {
                        VectorStoreSearchResult item;
                        item.id = ids_list[i].get<std::string>();
                        item.score = dist_list[i].get<double>(); 
                        item.payload = deserialize_payload(meta_list[i]);
                        if (emb_list.size() > i && emb_list[i].is_array()){
                           item.vector = emb_list[i].get<std::vector<float>>();
                        }
                        results.push_back(item);
                    }
                }
            }
        } catch (const nlohmann::json::exception& e) { // More specific catch for json errors
            throw std::runtime_error("ChromaDB: Failed to parse search response JSON: " + std::string(e.what()) + ". Body: " + (res ? res->body : "N/A"));
        }
        return results;
    }
    
    void ChromaVectorStore::delete_vector(const std::string& vector_id) {
        // Chroma uses POST for delete by IDs, with body: {"ids": ["id1", "id2"]}
        std::string api_path = "/api/v1/collections/" + collection_name_ + "/delete";
        nlohmann::json body = { {"ids", {vector_id}} };
        auto res = make_request("POST", api_path, body); 
        if (!res || res->status != 200) { // Chroma returns 200 on successful delete by ID
            std::string err_msg = "ChromaDB: Failed to delete vector '" + vector_id + "' from '" + collection_name_ + "'. ";
            if(res) err_msg += "Status: " + std::to_string(res->status) + ", Body: " + res->body;
            else err_msg += "Request Error: " + httplib::to_string(res.error());
            throw std::runtime_error(err_msg);
        }
    }

    void ChromaVectorStore::update_vector(const std::string& vector_id, const std::optional<std::vector<float>>& vector, const std::optional<std::map<std::string, std::any>>& payload) {
        // Chroma's "upsert" is the typical way to update.
        // Or use "add" which also overwrites based on ID.
        std::string api_path = "/api/v1/collections/" + collection_name_ + "/upsert"; 
        nlohmann::json item_to_upsert;
        item_to_upsert["ids"] = {vector_id};
        if (vector.has_value()) {
            item_to_upsert["embeddings"] = {vector.value()};
        }
        if (payload.has_value()) {
            item_to_upsert["metadatas"] = {serialize_payload(payload.value())};
        }
        
        if (!vector.has_value() && !payload.has_value()) {
            std::cout << "ChromaDB: Update called for vector_id '" << vector_id << "' without new vector or payload. No action taken." << std::endl;
            return;
        }

        auto res = make_request("POST", api_path, item_to_upsert);
         if (!res || res->status != 200) { // Upsert returns 200
            std::string err_msg = "ChromaDB: Failed to update/upsert vector '" + vector_id + "' in '" + collection_name_ + "'. ";
            if(res) err_msg += "Status: " + std::to_string(res->status) + ", Body: " + res->body;
            else err_msg += "Request Error: " + httplib::to_string(res.error());
            throw std::runtime_error(err_msg);
        }
    }

    std::optional<VectorStoreData> ChromaVectorStore::get_vector(const std::string& vector_id) {
        std::string api_path = "/api/v1/collections/" + collection_name_ + "/get";
        nlohmann::json body = { {"ids", {vector_id}}, {"include", {"metadatas", "embeddings"}} };

        auto res = make_request("POST", api_path, body);
        if (!res || res->status != 200) {
            std::cerr << "ChromaDB: Failed to get vector '" << vector_id << "'. Status: " 
                      << (res ? std::to_string(res->status) : "N/A") 
                      << ", Body: " << (res ? res->body : "N/A") << std::endl;
            return std::nullopt; 
        }

        try {
            nlohmann::json res_json = nlohmann::json::parse(res->body);
            // Expected structure for /get with one ID:
            // { "ids": ["id1"], "embeddings": [[0.1, ...]], "metadatas": [{"key": "val"}] }
            if (res_json.contains("ids") && res_json["ids"].is_array() && !res_json["ids"].get<std::vector<std::string>>().empty()) {
                VectorStoreData item;
                item.id = res_json["ids"].get<std::vector<std::string>>()[0];
                
                if (res_json.contains("metadatas") && res_json["metadatas"].is_array() && !res_json["metadatas"].empty() && res_json["metadatas"][0].is_object()){
                     item.payload = deserialize_payload(res_json["metadatas"][0]);
                }
                if (res_json.contains("embeddings") && res_json["embeddings"].is_array() && !res_json["embeddings"].empty() && res_json["embeddings"][0].is_array()){
                    item.vector = res_json["embeddings"][0].get<std::vector<float>>();
                } else if (res_json.contains("embeddings") && res_json["embeddings"].is_array() && !res_json["embeddings"].empty() && res_json["embeddings"][0].is_null()){
                    // Vector might be null if not stored or not requested properly
                     std::cerr << "ChromaDB: get_vector for '" << vector_id << "' returned null embedding." << std::endl;
                }
                return item;
            }
        } catch (const nlohmann::json::exception& e) { // More specific
            throw std::runtime_error("ChromaDB: Failed to parse get_vector response JSON for id '" + vector_id + "': " + std::string(e.what()) + ". Body: " + (res ? res->body : "N/A"));
        }
        return std::nullopt;
    }
    
    std::vector<std::string> ChromaVectorStore::list_collections() {
        std::string api_path = "/api/v1/collections";
        auto res = make_request("GET", api_path);
        if (!res || res->status != 200) {
            std::string err_msg = "ChromaDB: Failed to list collections. ";
            if(res) err_msg += "Status: " + std::to_string(res->status) + ", Body: " + res->body;
            else err_msg += "Request Error: " + httplib::to_string(res.error());
            throw std::runtime_error(err_msg);
        }
        std::vector<std::string> names;
        try {
            nlohmann::json res_json = nlohmann::json::parse(res->body);
            if (res_json.is_array()) {
                for (const auto& col : res_json) {
                    if (col.is_object() && col.contains("name") && col["name"].is_string()) {
                        names.push_back(col["name"].get<std::string>());
                    }
                }
            }
        } catch (const nlohmann::json::exception& e) { // More specific
            throw std::runtime_error("ChromaDB: Failed to parse list_collections response: " + std::string(e.what()) + ". Body: " + (res ? res->body : "N/A"));
        }
        return names;
    }

    void ChromaVectorStore::delete_collection(const std::string& name) {
        // API path: /api/v1/collections/{collection_name}
        std::string api_path = "/api/v1/collections/" + name;
        auto res = make_request("DELETE", api_path);
        // Successful delete is 200. 404 if collection not found.
        if (!res || (res->status != 200 && res->status != 404)) {
            std::string err_msg = "ChromaDB: Failed to delete collection '" + name + "'. ";
            if(res) err_msg += "Status: " + std::to_string(res->status) + ", Body: " + res->body;
            else err_msg += "Request Error: " + httplib::to_string(res.error());
            throw std::runtime_error(err_msg);
        }
        if (res && res->status == 404) {
            std::cout << "ChromaDB: Collection '" << name << "' not found for deletion." << std::endl;
        } else {
            std::cout << "ChromaDB: Collection '" << name << "' deleted." << std::endl;
        }
    }
    
    std::vector<VectorStoreData> ChromaVectorStore::list_vectors(const std::optional<std::map<std::string, std::any>>& filters, std::optional<int> limit) {
        // Chroma's GET /api/v1/collections/{collection_name}/get can list vectors with filters and limit.
        // Body for GET: {"where": {...}, "limit": N, "offset": M, "include": ["metadatas", "embeddings"]}
        std::string api_path = "/api/v1/collections/" + collection_name_ + "/get"; 
        nlohmann::json body = nlohmann::json::object(); // Needs to be an object for POST
        
        if (filters.has_value() && !filters.value().empty()) {
            body["where"] = serialize_payload(filters.value());
        }
        if (limit.has_value()) {
            body["limit"] = limit.value();
        }
        // To get all vectors, one might need to omit limit or use a very large number,
        // or handle pagination if the API supports it (e.g. with 'offset').
        // For now, if no limit is specified, we might fetch Chroma's default or a reasonable max.
        // The provided signature doesn't have offset.
        
        body["include"] = {"metadatas", "embeddings"}; // Also "documents" if needed

        auto res = make_request("POST", api_path, body); // Chroma's /get is a POST with body
         if (!res || res->status != 200) {
            std::string err_msg = "ChromaDB: Failed to list vectors from '" + collection_name_ + "'. ";
            if(res) err_msg += "Status: " + std::to_string(res->status) + ", Body: " + res->body;
            else err_msg += "Request Error: " + httplib::to_string(res.error());
            throw std::runtime_error(err_msg);
        }
        std::vector<VectorStoreData> results;
         try {
            nlohmann::json res_json = nlohmann::json::parse(res->body);
            // Structure is similar to get_vector but with multiple entries:
            // { "ids": ["id1", "id2", ...], "embeddings": [[...],[...],...], "metadatas": [{...},{...},...] }
            if (res_json.contains("ids") && res_json["ids"].is_array()) {
                const auto& ids_list = res_json["ids"].get<std::vector<std::string>>();
                const auto& meta_list_json = (res_json.contains("metadatas") && res_json["metadatas"].is_array()) ? res_json["metadatas"] : nlohmann::json::array();
                const auto& emb_list_json = (res_json.contains("embeddings") && res_json["embeddings"].is_array()) ? res_json["embeddings"] : nlohmann::json::array();

                for (size_t i = 0; i < ids_list.size(); ++i) {
                    VectorStoreData item;
                    item.id = ids_list[i];
                    if (meta_list_json.size() > i && meta_list_json[i].is_object()) {
                         item.payload = deserialize_payload(meta_list_json[i]);
                    }
                    if (emb_list_json.size() > i && emb_list_json[i].is_array()) {
                        item.vector = emb_list_json[i].get<std::vector<float>>();
                    } else if (emb_list_json.size() > i && emb_list_json[i].is_null()) {
                        // Vector can be null
                    }
                    results.push_back(item);
                }
            }
        } catch (const nlohmann::json::exception& e) { // More specific
            throw std::runtime_error("ChromaDB: Failed to parse list_vectors response JSON: " + std::string(e.what()) + ". Body: " + (res ? res->body : "N/A"));
        }
        return results;
    }

    void ChromaVectorStore::reset_collection() {
        // Delete and recreate the currently configured collection
        std::string current_collection = collection_name_; // Save in case of errors
        int current_dims = embedding_dims_.value_or(0); // Save current dims

        try {
            delete_collection(current_collection);
        } catch (const std::runtime_error& e) {
            std::cerr << "ChromaDB: Note during reset, could not delete collection '" << current_collection 
                      << "' (may not have existed or other error): " << e.what() << std::endl;
        }
        // Re-create with the same name and original dimension/distance settings
        // Assuming default distance "cosine" or "l2" is fine if not specified.
        // The constructor logic for create_collection handles setting distance.
        create_collection(current_collection, current_dims, "cosine"); 
    }

} // namespace mem0::vector_stores
