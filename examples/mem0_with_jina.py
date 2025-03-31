import os
from mem0 import Memory

# Set your Jina API key
# You can get one from https://chat.jina.ai/api
api_key = os.environ.get("JINA_API_KEY")
if not api_key:
    print("Please set your JINA_API_KEY environment variable")
    print("You can get one from https://chat.jina.ai/api")
    exit(1)

# Define the configuration
config = {
    "llm": {
        "provider": "jina",
        "config": {
            "model": "jina-chat-v1",  # This is the default model
            "temperature": 0.1,       # Lower temperature for more deterministic responses
            "max_tokens": 2000,       # Maximum number of tokens in the response
            "api_key": api_key,       # Your Jina API key
            # Optionally, you can specify a custom base URL if needed
            # "jina_base_url": "https://custom.jina.ai/v1/chat",
        }
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "text-embedding-3-small"
        }
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "mem0_jina_example",
            "embedding_model_dims": 1536,  # Dimensions of the OpenAI embedding model
        }
    },
    "version": "v1.1"
}

# Initialize Memory with the configuration
memory = Memory.from_config(config)

# Test adding a memory
user_id = "test-user-1"
message = "Jina AI is a powerful LLM with a developer-friendly API."

print(f"Adding memory: {message}")
result = memory.add(
    message,
    user_id=user_id,
    infer=True  # This will extract facts from the message
)
print("Added memory:")
print(result)

# Test searching for a memory
query = "What is Jina AI?"
print(f"\nSearching for: {query}")
search_results = memory.search(query, user_id=user_id)
print("Search results:")
for result in search_results:
    print(f"- {result.payload['data']}")

# Test using the LLM to chat
print("\nChatting with Jina AI:")
response = memory.chat("Tell me about Jina AI and its features.")
print(f"Response: {response}")

# Clean up (optional)
print("\nCleaning up...")
memory.delete_all(user_id=user_id)
print("Memories deleted.") 