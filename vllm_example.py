"""
Simple vLLM usage example with mem0
Shows how to use vLLM provider just like any other provider

Prerequisites:
1. Start vLLM server: vllm serve gpt2 --port 8000 --device cpu
2. Set GOOGLE_API_KEY for Gemini embeddings
"""

import os
import sys

# Use our local mem0 implementation
sys.path.insert(0, '.')

from mem0 import Memory

def main():
    """Simple example using vLLM with mem0"""

    # Set API keys (you can also set these as environment variables)
    os.environ["GOOGLE_API_KEY"] = "your-gemini-api-key-here"  # Replace with real key
    # os.environ["VLLM_BASE_URL"] = "http://localhost:8000/v1"  # Optional: set vLLM URL
    # os.environ["VLLM_API_KEY"] = "your-vllm-api-key"         # Optional: set vLLM API key

    print("🚀 vLLM + mem0 Example")
    print("=" * 30)

    # Simple configuration - just like other providers
    config = {
        "llm": {
            "provider": "vllm",
            "config": {
                "model": "gpt2",                              # Model on your vLLM server
                "vllm_base_url": "http://localhost:8000/v1",  # vLLM server URL (or use VLLM_BASE_URL env var)
                "temperature": 0.7,
                "max_tokens": 100,
            }
        },
        "embedder": {
            "provider": "gemini",
            "config": {
                "model": "models/text-embedding-004"
            }
        }
    }
    
    # Initialize memory - same as any other provider
    print("📝 Initializing memory with vLLM...")
    memory = Memory.from_config(config)
    print("✅ Memory initialized!")
    
    # Use it exactly like with any other provider
    print("\n💾 Adding memories...")
    
    # Add some memories
    memory.add("I love playing chess on weekends", user_id="alice")
    memory.add("I'm learning Python programming", user_id="alice") 
    memory.add("My favorite food is pizza", user_id="alice")
    
    print("✅ Memories added!")
    
    # Search memories
    print("\n🔍 Searching memories...")
    
    results = memory.search("What does Alice like to do?", user_id="alice")
    
    print(f"Found {len(results)} memories:")
    for i, result in enumerate(results, 1):
        print(f"  {i}. {result['memory']}")
    
    print("\n🎉 vLLM integration working perfectly!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure vLLM server is running: vllm serve gpt2 --port 8000")
        print("2. Set GOOGLE_API_KEY for Gemini embeddings")
        print("3. Check server health: curl http://localhost:8000/health")
