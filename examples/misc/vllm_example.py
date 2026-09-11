"""Example of using vLLM with Mem0 for inferred memory extraction.

SETUP INSTRUCTIONS:
1. Install Mem0 and vLLM:
   pip install mem0ai
   pip install vllm

2. Start vLLM server (in a separate terminal):
   vllm serve Qwen/Qwen3-8B --port 8000 --max-model-len 16384

3. Set an OpenAI API key for the embedding model:
   export OPENAI_API_KEY="your-openai-api-key"

4. Verify the vLLM server is running:
   curl http://localhost:8000/health

5. Run this example:
   python examples/misc/vllm_example.py

To enable LMCache, start vLLM with the LMCache MP connector documented at:
https://docs.mem0.ai/components/llms/models/vllm

Optional environment variables:
   export VLLM_MODEL="Qwen/Qwen3-8B"
   export VLLM_BASE_URL="http://localhost:8000/v1"
   export VLLM_API_KEY="vllm-api-key"
   export QDRANT_PATH="/tmp/mem0_vllm_example"
"""

import os

from mem0 import Memory

MODEL = os.getenv("VLLM_MODEL", "Qwen/Qwen3-8B")
BASE_URL = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
VLLM_API_KEY = os.getenv("VLLM_API_KEY", "vllm-api-key")
QDRANT_PATH = os.getenv("QDRANT_PATH", "/tmp/mem0_vllm_example")
USER_ID = "vllm_example_user"

# LMCache is configured on the vLLM server, so this Mem0 configuration works
# with either native vLLM or an LMCache-backed vLLM server.
config = {
    "llm": {
        "provider": "vllm",
        "config": {
            "model": MODEL,
            "vllm_base_url": BASE_URL,
            "api_key": VLLM_API_KEY,
            "temperature": 0.1,
            "max_tokens": 500,
        },
    },
    "embedder": {"provider": "openai", "config": {"model": "text-embedding-3-small"}},
    "vector_store": {
        "provider": "qdrant",
        "config": {"collection_name": "vllm_memories", "path": QDRANT_PATH},
    },
    "history_db_path": ":memory:",
}


def main():
    """
    Demonstrate vLLM integration with Mem0.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY for the embedding model before running this example.")

    print(f"--> Initializing Mem0 with vLLM model {MODEL} at {BASE_URL}...")

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
            "user_id": USER_ID,
        },
        {
            "messages": [
                {"role": "user", "content": "I'm learning Python programming"},
                {
                    "role": "assistant",
                    "content": "Python is a fantastic language for beginners! What specific areas are you focusing on?",
                },
            ],
            "user_id": USER_ID,
        },
        {
            "messages": [
                {"role": "user", "content": "I prefer working late at night, I'm more productive then"},
                {
                    "role": "assistant",
                    "content": "Many people find they're more creative and focused during nighttime hours. It's important to maintain a consistent schedule that works for you.",
                },
            ],
            "user_id": USER_ID,
        },
    ]

    print("\n--> Adding memories using vLLM...")

    # Inferred adds call vLLM to extract memories. With LMCache enabled on the
    # server, these calls can reuse the shared extraction-prompt prefix.
    for i, conversation in enumerate(conversations, 1):
        result = memory.add(messages=conversation["messages"], user_id=conversation["user_id"])
        print(f"Memory {i} added: {result}")

    print("\n🔍 Searching memories...")

    # Normal search uses the configured embedder and vector store, not vLLM.
    search_queries = [
        "What does the user like to do on weekends?",
        "What is the user learning?",
        "When is the user most productive?",
    ]

    for query in search_queries:
        print(f"\nQuery: {query}")
        memories = memory.search(query=query, filters={"user_id": USER_ID})["results"]

        for memory_item in memories:
            print(f"  - {memory_item['memory']}")

    print("\n--> Getting all memories for user...")
    all_memories = memory.get_all(filters={"user_id": USER_ID})["results"]
    print(f"Total memories stored: {len(all_memories)}")

    for memory_item in all_memories:
        print(f"  - {memory_item['memory']}")

    print("\n--> vLLM integration demo completed successfully!")
    print("    LMCache, when enabled on the server, requires no Mem0 code changes.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"=> Error: {e}")
        print("\nTroubleshooting:")
        print(f"1. Make sure vLLM is serving {MODEL} at {BASE_URL}")
        print("2. Check if the model is downloaded and accessible")
        print("3. Verify OPENAI_API_KEY is set for embeddings")
        print("4. Verify the base URL and port configuration")
        raise SystemExit(1) from e
