"""
Example of using vLLM with mem0 for high-performance memory operations.

SETUP INSTRUCTIONS:
1. Install vLLM:
   pip install vllm

2. Start vLLM server (in a separate terminal):
   vllm serve microsoft/DialoGPT-small --port 8000

   Wait for the message: "Uvicorn running on http://0.0.0.0:8000"
   (Small model: ~500MB download, much faster!)

3. Verify server is running:
   curl http://localhost:8000/health

4. Run this example:
   python examples/misc/vllm_example.py

Optional environment variables:
   export VLLM_BASE_URL="http://localhost:8000/v1"
   export VLLM_API_KEY="vllm-api-key"
"""

from mem0 import Memory

# Configuration for vLLM integration
config = {
    "llm": {
        "provider": "vllm",
        "config": {
            "model": "Qwen/Qwen2.5-32B-Instruct",
            "vllm_base_url": "http://localhost:8000/v1",
            "api_key": "vllm-api-key",
            "temperature": 0.7,
            "max_tokens": 100,
        },
    },
    "embedder": {"provider": "openai", "config": {"model": "text-embedding-3-small"}},
    "vector_store": {
        "provider": "qdrant",
        "config": {"collection_name": "vllm_memories", "host": "localhost", "port": 6333},
    },
}


def main():
    """
    Demonstrate vLLM integration with mem0
    """
    print("--> Initializing mem0 with vLLM...")

    # Initialize memory with vLLM
    memory = Memory.from_config(config)

    print("--> Memory initialized successfully!")

    # Example conversations to store
    conversations = [
        {
            "messages": [
                {"role": "user", "content": "I love playing chess on weekends"},
                {
                    "role": "assistant",
                    "content": "That's great! Chess is an excellent strategic game that helps improve critical thinking.",
                },
            ],
            "user_id": "user_123",
        },
        {
            "messages": [
                {"role": "user", "content": "I'm learning Python programming"},
                {
                    "role": "assistant",
                    "content": "Python is a fantastic language for beginners! What specific areas are you focusing on?",
                },
            ],
            "user_id": "user_123",
        },
        {
            "messages": [
                {"role": "user", "content": "I prefer working late at night, I'm more productive then"},
                {
                    "role": "assistant",
                    "content": "Many people find they're more creative and focused during nighttime hours. It's important to maintain a consistent schedule that works for you.",
                },
            ],
            "user_id": "user_123",
        },
    ]

    print("\n--> Adding memories using vLLM...")

    # Add memories - now powered by vLLM's high-performance inference
    for i, conversation in enumerate(conversations, 1):
        result = memory.add(messages=conversation["messages"], user_id=conversation["user_id"])
        print(f"Memory {i} added: {result}")

    print("\n🔍 Searching memories...")

    # Search memories - vLLM will process the search and memory operations
    search_queries = [
        "What does the user like to do on weekends?",
        "What is the user learning?",
        "When is the user most productive?",
    ]

    for query in search_queries:
        print(f"\nQuery: {query}")
        memories = memory.search(query=query, user_id="user_123")

        for memory_item in memories:
            print(f"  - {memory_item['memory']}")

    print("\n--> Getting all memories for user...")
    all_memories = memory.get_all(user_id="user_123")
    print(f"Total memories stored: {len(all_memories)}")

    for memory_item in all_memories:
        print(f"  - {memory_item['memory']}")

    print("\n--> vLLM integration demo completed successfully!")
    print("\nBenefits of using vLLM:")
    print("  -> 2.7x higher throughput compared to standard implementations")
    print("  -> 5x faster time-per-output-token")
    print("  -> Efficient memory usage with PagedAttention")
    print("  -> Simple configuration, same as other providers")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"=> Error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure vLLM server is running: vllm serve microsoft/DialoGPT-small --port 8000")
        print("2. Check if the model is downloaded and accessible")
        print("3. Verify the base URL and port configuration")
        print("4. Ensure you have the required dependencies installed")
