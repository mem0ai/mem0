from mem0 import Memory
import dotenv
import os
dotenv.load_dotenv()

config = {
    "vector_store": {
        "provider": "elasticsearch",
        "config": {
            "host": os.getenv("ES_URL"),
            "user": os.getenv("ES_USERNAME"),
            "password": os.getenv("ES_PASSWORD"),
            "collection_name": "memories",
            "embedding_model_dims": 1536,
            "use_ssl": True,
            "verify_certs": True,
            "port": 443
        }
    }
}

def main():
    # Initialize memory
    memory = Memory.from_config(config)
    
    try:
        # Add test memory
        memory.add("This is a test memory", user_id="test_user")
        print("Successfully added test memory")
        
        # Test retrieval
        
        user_memories = memory.get_all(user_id="test_user")
        print("\nTest user memories:", user_memories)
        
        similar_memories = memory.search("test memory", user_id="test_user", limit=5)
        print("\nSimilar memories:", similar_memories)
        
    except Exception as e:
        print(f"Error occurred: {str(e)}")

if __name__ == "__main__":
    main()