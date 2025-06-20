"""
MongoDB Atlas Vector Store with OpenAI Integration Example

This example demonstrates how to use mem0 with MongoDB Atlas Vector Store and OpenAI models.
It showcases memory storage, retrieval, and intelligent search capabilities using:
- MongoDB Atlas Vector Search for scalable vector storage
- OpenAI LLM for memory processing
- OpenAI Embedding Model for high-quality vector embeddings

Prerequisites:
1. MongoDB Atlas account with a cluster (free tier M0 works)
2. OpenAI API key for both LLM and embeddings
3. Environment variables: MONGODB_URI, OPENAI_API_KEY

Connection Methods:
- Method 1 (Recommended): Use MONGODB_URI environment variable
- Method 2: Use individual credentials (MONGO_HOST, MONGO_USER, MONGO_PASSWORD)

Example usage:
    # Method 1: Connection URI
    export MONGODB_URI="mongodb+srv://user:pass@cluster.mongodb.net/"
    export OPENAI_API_KEY="your_openai_api_key"
    python mongodb_atlas_openai_example.py

    # Method 2: Individual credentials
    export MONGO_HOST="localhost"
    export MONGO_USER="myuser"
    export MONGO_PASSWORD="mypass"
    export OPENAI_API_KEY="your_openai_api_key"
    python mongodb_atlas_openai_example.py
"""

import os
from mem0 import Memory


def create_memory_config():
    """Create mem0 configuration with MongoDB Atlas and OpenAI models."""
    openai_key = os.getenv("OPENAI_API_KEY")
    mongodb_uri = os.getenv("MONGODB_URI")

    if not openai_key:
        raise ValueError("OPENAI_API_KEY environment variable is required")

    # Method 1: Connection URI (Recommended)
    if mongodb_uri:
        vector_store_config = {
            "db_name": "mem0_db",
            "collection_name": "memories",
            "embedding_model_dims": 1536,  # Must match embedder dimensions
            "mongo_uri": mongodb_uri
        }
    else:
        # Method 2: Individual credentials
        mongo_host = os.getenv("MONGO_HOST", "localhost")
        mongo_user = os.getenv("MONGO_USER")
        mongo_password = os.getenv("MONGO_PASSWORD")
        mongo_port = int(os.getenv("MONGO_PORT", "27017"))

        vector_store_config = {
            "db_name": "mem0_db",
            "collection_name": "memories",
            "embedding_model_dims": 1536,
            "host": mongo_host,
            "port": mongo_port
        }

        # Add credentials if provided
        if mongo_user and mongo_password:
            vector_store_config.update({
                "user": mongo_user,
                "password": mongo_password
            })

    return {
        "llm": {
            "provider": "openai",
            "config": {
                "model": "gpt-4o-mini",  # Cost-effective, high-performance model
                "temperature": 0.2,
                "max_tokens": 1000,
                "api_key": openai_key
            }
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": "text-embedding-3-small",  # Latest embedding model
                "embedding_dims": 1536,  # OpenAI embedding dimensions
                "api_key": openai_key
            }
        },
        "vector_store": {
            "provider": "mongodb",
            "config": vector_store_config
        }
    }


def add_user_memories(memory, user_id):
    """Add sample user memories to demonstrate the system."""
    conversations = [
        {
            "messages": [
                {"role": "user", "content": "Hi, I'm Alice. I love reading science fiction novels."},
                {"role": "assistant", "content": "Hello Alice! Science fiction is fascinating. Do you have any favorite authors?"},
                {"role": "user", "content": "I really enjoy Isaac Asimov's Foundation series and Philip K. Dick's works."},
                {"role": "assistant", "content": "Excellent choices! Both are masters of the genre."}
            ]
        },
        {
            "messages": [
                {"role": "user", "content": "I'm planning a trip to Japan next month."},
                {"role": "assistant", "content": "That sounds exciting! What are you most looking forward to?"},
                {"role": "user", "content": "I want to visit traditional temples and experience a tea ceremony."},
                {"role": "assistant", "content": "Kyoto would be perfect for that! It has beautiful temples and authentic tea ceremonies."}
            ]
        },
        {
            "messages": [
                {"role": "user", "content": "I've been learning Python programming lately."},
                {"role": "assistant", "content": "That's great! Python is very versatile. What are you working on?"},
                {"role": "user", "content": "Mainly data science projects with pandas and numpy."},
                {"role": "assistant", "content": "Perfect! Those are essential libraries for data science."}
            ]
        }
    ]
    
    print("--> Adding user memories...")
    for i, conv in enumerate(conversations, 1):
        result = memory.add(conv["messages"], user_id=user_id)
        # Handle both dict and list response formats
        if isinstance(result, dict) and 'results' in result:
            count = len(result['results'])
        else:
            count = len(result) if result else 0
        print(f"--> Added conversation {i}: {count} memories created")
    
    return len(conversations)


def search_memories(memory, user_id):
    """Demonstrate memory search functionality."""
    search_queries = [
        "What books does Alice like to read?",
        "Where is Alice planning to travel?",
        "What programming skills does Alice have?",
        "What are Alice's interests and hobbies?"
    ]
    
    print("\n--> Searching memories...")
    for query in search_queries:
        print(f"\n--> Query: '{query}'")
        search_response = memory.search(query, user_id=user_id)
        
        # Handle the response format: {'results': [...]}
        if isinstance(search_response, dict) and 'results' in search_response:
            results = search_response['results']
        else:
            results = search_response if search_response else []
        
        if results:
            for j, result in enumerate(results, 1):
                if isinstance(result, dict):
                    memory_text = result.get('memory', str(result))
                    score = result.get('score', 'N/A')
                    if isinstance(score, (int, float)):
                        print(f"  {j}. {memory_text} (Score: {score:.3f})")
                    else:
                        print(f"  {j}. {memory_text}")
                else:
                    print(f"  {j}. {str(result)}")
        else:
            print("  No results found")


def get_all_memories(memory, user_id):
    """Retrieve and display all memories for a user."""
    print(f"\n--> All memories for user '{user_id}':")
    all_memories_response = memory.get_all(user_id=user_id)
    
    # Handle the response format: {'results': [...]}
    if isinstance(all_memories_response, dict) and 'results' in all_memories_response:
        all_memories = all_memories_response['results']
    else:
        all_memories = all_memories_response if all_memories_response else []
        
    if all_memories:
        for i, mem in enumerate(all_memories, 1):
            if isinstance(mem, dict):
                memory_text = mem.get('memory', str(mem))
                print(f"  {i}. {memory_text}")
            else:
                print(f"  {i}. {str(mem)}")
    else:
        print("  No memories found")
    
    return len(all_memories)


def main():
    """Main function demonstrating MongoDB Atlas + OpenAI integration."""
    print("-" * 60)
    print("MongoDB Atlas + OpenAI Integration Demo")
    print("-" * 60)
    
    # Check environment variables
    mongodb_uri = os.getenv("MONGODB_URI")
    openai_key = os.getenv("OPENAI_API_KEY")

    # Check for MongoDB connection (either URI or individual credentials)
    mongo_host = os.getenv("MONGO_HOST")
    mongo_user = os.getenv("MONGO_USER")
    mongo_password = os.getenv("MONGO_PASSWORD")

    if not mongodb_uri and not mongo_host:
        print("❌ Missing MongoDB connection configuration!")
        print("   Method 1: Set MONGODB_URI environment variable")
        print("   Method 2: Set MONGO_HOST (and optionally MONGO_USER, MONGO_PASSWORD)")
        return

    if not openai_key:
        print("❌ Missing required environment variable: OPENAI_API_KEY")
        print("   Get your API key from https://platform.openai.com/api-keys")
        return

    # Show connection method being used
    if mongodb_uri:
        print(f"--> Using MongoDB connection URI (Method 1)")
    else:
        print(f"--> Using individual credentials (Method 2): {mongo_host}")
        if mongo_user:
            print(f"    Authentication: {mongo_user}")
        else:
            print(f"    Authentication: None")
    
    try:
        # Create memory instance
        print("--> Initializing mem0 with MongoDB Atlas and OpenAI...")
        config = create_memory_config()
        memory = Memory.from_config(config)
        print("--> Memory instance created successfully")
        
        # Demonstrate functionality
        user_id = "alice_demo"
        
        # Add memories
        conversations_added = add_user_memories(memory, user_id)
        
        # Search memories
        search_memories(memory, user_id)
        
        # Get all memories
        total_memories = get_all_memories(memory, user_id)
        
        # Summary
        print(f"\n🎉 Demo completed successfully!")
        print(f"-> Summary:")
        print(f"   - Conversations processed: {conversations_added}")
        print(f"   - Total memories stored: {total_memories}")
        print(f"   - Vector store: MongoDB Atlas")
        print(f"   - LLM: OpenAI GPT-4o-mini")
        print(f"   - Embeddings: OpenAI text-embedding-3-small")
        print(f"   - Architecture: Production-stable, no SSL issues")
        
    except Exception as e:
        print(f"Error during demo: {str(e)}")
        print("Please check your configuration and try again.")


if __name__ == "__main__":
    main()
