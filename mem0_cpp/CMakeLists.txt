cmake_minimum_required(VERSION 3.15)
project(Mem0Cpp VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)
set(CMAKE_CXX_EXTENSIONS OFF)

# Include FetchContent module
include(FetchContent)

# Fetch nlohmann_json
FetchContent_Declare(
  nlohmann_json
  GIT_REPOSITORY https://github.com/nlohmann/json.git
  GIT_TAG v3.11.3 # Or a more recent stable version
)
FetchContent_MakeAvailable(nlohmann_json)

# Fetch cpp-httplib
# Forcing SSL to be ON for httplib
set(CPPHTTPLIB_OPENSSL_SUPPORT ON CACHE BOOL "Enable SSL for httplib" FORCE)
FetchContent_Declare(
  cpp_httplib
  GIT_REPOSITORY https://github.com/yhirose/cpp-httplib.git
  GIT_TAG v0.15.3 # Or a more recent stable version
)
FetchContent_MakeAvailable(cpp_httplib)


# --- Main Library ---
add_library(mem0
    src/embeddings/openai_embedding.cpp
    src/llms/openai_llm.cpp 
    src/vector_stores/chroma_vector_store.cpp
    # Add other .cpp files here as they are created
)
target_include_directories(mem0 PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include> # For installing
)

# Link dependencies that mem0 itself needs
target_link_libraries(mem0 PUBLIC nlohmann_json::nlohmann_json) 
target_link_libraries(mem0 PUBLIC httplib::httplib) # httplib creates a target 'httplib::httplib'

# --- Executable for testing ---
add_executable(mem0_test_app src/main.cpp)
target_link_libraries(mem0_test_app PRIVATE mem0) # Link against our library

# Placeholder for tests
# enable_testing()
# add_subdirectory(tests)

message(STATUS "Mem0Cpp project configured with nlohmann/json and cpp-httplib")
