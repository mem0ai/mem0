#include "mem0/llms/openai_llm.h"
#include <iostream> 
#include <stdexcept>
#include <cstdlib>   // For std::getenv

namespace mem0::llms {

    OpenAILLM::OpenAILLM(const configs::BaseLlmConfig& config)
        : LLMBase(config) {

        if (std::getenv("OPENROUTER_API_KEY")) {
            use_openrouter_ = true;
            api_key_ = std::getenv("OPENROUTER_API_KEY");
            base_url_ = config.openrouter_base_url.value_or("openrouter.ai"); // host only
            api_path_ = "/api/v1/chat/completions"; // Common path for OpenRouter
            openrouter_models_ = config.models;
            openrouter_route_ = config.route;
            openrouter_site_url_ = config.site_url;
            openrouter_app_name_ = config.app_name;
        } else {
            use_openrouter_ = false;
            api_key_ = config.api_key.value_or("");
            if (api_key_.empty()) {
                const char* env_api_key = std::getenv("OPENAI_API_KEY");
                if (env_api_key) {
                    api_key_ = env_api_key;
                }
            }
            if (api_key_.empty()) {
                throw std::runtime_error("OpenAI API key not provided in config or OPENAI_API_KEY/OPENROUTER_API_KEY environment variable.");
            }
            base_url_ = config.openai_base_url.value_or("api.openai.com"); // host only
        }
        
        model_name_ = config.model.value_or(use_openrouter_ ? "" : "gpt-4o-mini"); // Default for OpenAI, empty for OpenRouter if models are specified

        // Normalize base_url (remove scheme)
        if (base_url_.rfind("https://", 0) == 0) {
            base_url_ = base_url_.substr(8);
        } else if (base_url_.rfind("http://", 0) == 0) {
            base_url_ = base_url_.substr(7);
        }
    }

    LLMResponse OpenAILLM::parse_openai_response(const httplib::Result& res, bool has_tools) {
        LLMResponse llm_response;
        try {
            nlohmann::json response_json = nlohmann::json::parse(res->body);

            if (response_json.contains("choices") && response_json["choices"].is_array() && !response_json["choices"].empty()) {
                const auto& first_choice = response_json["choices"][0];
                if (first_choice.contains("message")) {
                    const auto& message = first_choice["message"];
                    if (message.contains("content") && !message["content"].is_null()) {
                        llm_response.content = message["content"].get<std::string>();
                    }

                    if (has_tools && message.contains("tool_calls") && message["tool_calls"].is_array()) {
                        for (const auto& tool_call_json : message["tool_calls"]) {
                            ToolCall tc;
                            if (tool_call_json.contains("function") && tool_call_json["function"].contains("name")) {
                                tc.name = tool_call_json["function"]["name"].get<std::string>();
                                if (tool_call_json["function"].contains("arguments")) {
                                    try {
                                        // nlohmann::json::get<std::map<std::string, std::any>> is not directly supported.
                                        // We need to manually iterate or use a library that bridges nlohmann::json and std::any.
                                        // For simplicity, we'll parse to map<string, nlohmann::json> and then convert known types to std::any.
                                        nlohmann::json args_json = nlohmann::json::parse(tool_call_json["function"]["arguments"].get<std::string>());
                                        for (auto& [key, value] : args_json.items()) {
                                            if (value.is_string()) {
                                                tc.arguments[key] = value.get<std::string>();
                                            } else if (value.is_number_integer()) {
                                                tc.arguments[key] = value.get<int64_t>(); // Or int, depending on expected range
                                            } else if (value.is_number_float()) {
                                                tc.arguments[key] = value.get<double>();
                                            } else if (value.is_boolean()) {
                                                tc.arguments[key] = value.get<bool>();
                                            } else if (value.is_null()) {
                                                // tc.arguments[key] = nullptr; // std::any cannot hold nullptr directly unless it's typed
                                            } else {
                                                // For complex types (objects, arrays), store as string or nlohmann::json object
                                                tc.arguments[key] = value.dump(); 
                                            }
                                        }
                                    } catch (const nlohmann::json::parse_error& e) {
                                        std::cerr << "Warning: Could not parse tool call arguments string: " << e.what() << std::endl;
                                        // Optionally, store the raw string if parsing fails
                                        // tc.arguments["raw_arguments_json_string"] = tool_call_json["function"]["arguments"].get<std::string>();
                                    } catch (const nlohmann::json::type_error& e_type) {
                                         std::cerr << "Warning: Type error during tool call argument conversion: " << e_type.what() << std::endl;
                                    }
                                }
                            }
                            llm_response.tool_calls.push_back(tc);
                        }
                    }
                }
            }
            // It's valid for an LLM response to have only tool_calls and no textual content.
            if (!llm_response.content.has_value() && llm_response.tool_calls.empty()) {
                 // Check if it's a valid case of no content and no tools (e.g. stop reason is length)
                 // Or if the structure itself is missing key parts like "choices"
                 if (!response_json.contains("choices") || response_json["choices"].empty()) {
                    throw std::runtime_error("Invalid or empty response structure from OpenAI API (missing choices): " + res->body);
                 }
            }
            return llm_response;

        } catch (const nlohmann::json::parse_error& e) {
            throw std::runtime_error("Failed to parse JSON response from OpenAI API: " + std::string(e.what()) + ". Response body: " + res->body);
        }
    }


    LLMResponse OpenAILLM::generate_response(
        const std::vector<std::map<std::string, std::string>>& messages,
        const std::optional<std::string>& response_format_type,
        const std::optional<std::vector<std::map<std::string, std::any>>>& tools,
        const std::string& tool_choice) {

        httplib::SSLClient cli(base_url_.c_str());
        cli.set_connection_timeout(60); 
        cli.set_read_timeout(300);      
        cli.set_write_timeout(60);   
        
        httplib::Headers headers;
        headers.emplace("Authorization", "Bearer " + api_key_);
        headers.emplace("Content-Type", "application/json");

        if (use_openrouter_) {
            if (openrouter_site_url_.has_value()) { // HTTP-Referer is common
                 headers.emplace("HTTP-Referer", openrouter_site_url_.value());
            }
            if (openrouter_app_name_.has_value()) { // X-Title is also common for identifying app
                 headers.emplace("X-Title", openrouter_app_name_.value());
            }
        }
        // Note: set_default_headers will clear existing ones, so add all at once or use multiple emplace if supported
        // For httplib, it's better to build a Headers object and then pass it to set_default_headers
        cli.set_default_headers(headers);


        nlohmann::json body;
        body["messages"] = messages;
        
        if (use_openrouter_) {
            if (openrouter_models_.has_value() && !openrouter_models_->empty()) {
                // If 'models' is a list of more than one, it implies a route.
                // If 'models' is a list with one model, it's like specifying a single model.
                if(openrouter_models_->size() > 1 && openrouter_route_.has_value()) {
                     body["models"] = openrouter_models_.value(); // OpenRouter specific: array of models
                     body["route"] = openrouter_route_.value();   // OpenRouter specific: "fallback", "random" etc.
                } else if (!openrouter_models_->empty()){ 
                     body["model"] = openrouter_models_->front(); // Use the first model
                } else if (!model_name_.empty()){ 
                     body["model"] = model_name_; // Fallback to single model_name_ if 'models' list is empty
                } else {
                     throw std::runtime_error("OpenRouter requires either 'models' list (non-empty) or a 'model' name to be specified.");
                }
            } else if (!model_name_.empty()) { 
                 body["model"] = model_name_;
            } else {
                throw std::runtime_error("OpenRouter requires either 'models' list or a 'model' to be specified.");
            }
        } else { // Standard OpenAI
            body["model"] = model_name_;
        }
        
        body["temperature"] = config_.temperature;
        body["max_tokens"] = config_.max_tokens;
        body["top_p"] = config_.top_p;

        if (response_format_type.has_value()) {
            body["response_format"] = { {"type", response_format_type.value()} };
        }

        bool has_tools = false;
        if (tools.has_value() && !tools.value().empty()) {
            // The 'tools' field in OpenAI API expects an array of objects.
            // Each object has a "type" (e.g., "function") and a "function" object.
            // The "function" object has "name", "description", and "parameters".
            // std::vector<std::map<std::string, std::any>> needs careful conversion to nlohmann::json
            // This is a simplified conversion. A robust solution might need a recursive std::any_to_json function.
            nlohmann::json tools_json_array = nlohmann::json::array();
            for (const auto& tool_spec_map : tools.value()) {
                nlohmann::json tool_json_obj;
                if (tool_spec_map.count("type")) {
                    try {
                        tool_json_obj["type"] = std::any_cast<std::string>(tool_spec_map.at("type"));
                    } catch (const std::bad_any_cast& e) { /* log or handle error */ }
                }
                if (tool_spec_map.count("function")) {
                    try {
                        // Assuming "function" is std::map<std::string, std::any>
                        auto func_details_any = tool_spec_map.at("function");
                        auto func_details_map = std::any_cast<std::map<std::string, std::any>>(func_details_any);
                        
                        nlohmann::json function_json_obj;
                        if (func_details_map.count("name")) {
                             function_json_obj["name"] = std::any_cast<std::string>(func_details_map.at("name"));
                        }
                        if (func_details_map.count("description")) {
                             function_json_obj["description"] = std::any_cast<std::string>(func_details_map.at("description"));
                        }
                        if (func_details_map.count("parameters")) {
                            // Parameters should be a JSON schema object.
                            // Assuming it's already a map that can be converted to nlohmann::json.
                            // This part is highly dependent on how parameters are structured in std::any.
                            // If parameters are map<string, any>, a recursive conversion is needed.
                            // For now, let's assume it's directly convertible or a pre-made nlohmann::json object.
                            auto params_any = func_details_map.at("parameters");
                            if (params_any.type() == typeid(nlohmann::json) ) {
                                function_json_obj["parameters"] = std::any_cast<nlohmann::json>(params_any);
                            } else {
                                // Fallback or error: Parameters are not in expected nlohmann::json format
                                // This might require a more sophisticated std::any to json conversion.
                                // For now, an empty object or error.
                                function_json_obj["parameters"] = nlohmann::json::object(); 
                                std::cerr << "Warning: Tool parameters are not in nlohmann::json format, using empty object." << std::endl;
                            }
                        }
                         tool_json_obj["function"] = function_json_obj;
                    } catch (const std::bad_any_cast& e) { 
                        std::cerr << "Error converting tool function details: " << e.what() << std::endl;
                    }
                }
                tools_json_array.push_back(tool_json_obj);
            }
            body["tools"] = tools_json_array;
            body["tool_choice"] = tool_choice; // e.g. "auto", "none", or {"type": "function", "function": {"name": "my_function"}}
            has_tools = true;
        }
        
        std::string body_str = body.dump();
        
        auto res = cli.Post(api_path_.c_str(), body_str, "application/json");

        if (!res) {
            auto err = res.error();
            std::string err_msg = "HTTP request failed: " + httplib::to_string(err);
             if (err == httplib::Error::SSLLoadingCerts) {
                 err_msg += ". Ensure SSL certificates are available or correctly configured if using default system certs.";
            }
            throw std::runtime_error(err_msg);
        }

        if (res->status != 200) {
            throw std::runtime_error("OpenAI/OpenRouter API request failed with status " + std::to_string(res->status) + ": " + res->body);
        }
        
        return parse_openai_response(res, has_tools);
    }

} // namespace mem0::llms
