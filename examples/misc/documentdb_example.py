"""
Example demonstrating how to use Amazon DocumentDB as a vector store with Mem0.

Prerequisites:
1. Amazon DocumentDB cluster with vector search enabled
2. TLS certificate bundle downloaded from AWS
3. Proper network configuration (VPC, security groups)
4. Install dependencies: pip install pymongo mem0ai
"""

import os
from mem0 import Memory

# Set AWS credentials
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_ACCESS_KEY_ID"] = "your-access-key"
os.environ["AWS_SECRET_ACCESS_KEY"] = "your-secret-key"

# DocumentDB configuration with AWS Bedrock
config = {
    "embedder": {
        "provider": "aws_bedrock",
        "config": {
            "model": "amazon.titan-embed-text-v2:0"
        }
    },
    "llm": {
        "provider": "aws_bedrock",
        "config": {
            "model": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "temperature": 0.1,
            "max_tokens": 2000
        }
    },
    "vector_store": {
        "provider": "amazon_documentdb",
        "config": {
            "db_name": "mem0_db",
            "collection_name": "memories",
            "embedding_model_dims": 1024,  # Titan embedding dimensions
            "mongo_uri": "mongodb://username:password@docdb-cluster.cluster-xyz.us-west-2.docdb.amazonaws.com:27017/?tls=true&tlsCAFile=global-bundle.pem"
        }
    }
}

def main():
    # Initialize memory with DocumentDB
    memory = Memory.from_config(config)
    
    # Add some memories for different users
    print("Adding memories...")
    
    # User Alice - Tennis enthusiast
    memory.add("I love playing tennis and I'm working on improving my backhand.", user_id="alice")
    memory.add("I practice tennis every Tuesday and Thursday at the local club.", user_id="alice")
    memory.add("My favorite tennis player is Serena Williams.", user_id="alice")
    
    # User Bob - Software developer
    memory.add("I'm a Python developer working on machine learning projects.", user_id="bob")
    memory.add("I use PyTorch for deep learning and scikit-learn for traditional ML.", user_id="bob")
    memory.add("I'm currently learning about transformer architectures.", user_id="bob")
    
    # User Charlie - Chef
    memory.add("I'm a professional chef specializing in Italian cuisine.", user_id="charlie")
    memory.add("My signature dish is homemade pasta with truffle sauce.", user_id="charlie")
    memory.add("I source ingredients from local farmers markets.", user_id="charlie")
    
    print("Memories added successfully!")
    
    # Search for memories
    print("\n--- Searching for Alice's sports interests ---")
    alice_sports = memory.search("What sports does Alice like?", user_id="alice")
    for result in alice_sports['results']:
        print(f"Memory: {result['memory']}")
        print(f"Score: {result['score']:.3f}")
        print("---")
    
    print("\n--- Searching for Bob's programming skills ---")
    bob_programming = memory.search("What programming languages and frameworks does Bob use?", user_id="bob")
    for result in bob_programming['results']:
        print(f"Memory: {result['memory']}")
        print(f"Score: {result['score']:.3f}")
        print("---")
    
    print("\n--- Searching for Charlie's cooking expertise ---")
    charlie_cooking = memory.search("What type of cuisine does Charlie specialize in?", user_id="charlie")
    for result in charlie_cooking['results']:
        print(f"Memory: {result['memory']}")
        print(f"Score: {result['score']:.3f}")
        print("---")
    
    # Get all memories for a user
    print("\n--- All memories for Alice ---")
    alice_memories = memory.get_all(user_id="alice")
    for memory_item in alice_memories['results']:
        print(f"ID: {memory_item['id']}")
        print(f"Memory: {memory_item['memory']}")
        print("---")
    
    # Update a memory
    if alice_memories['results']:
        memory_id = alice_memories['results'][0]['id']
        print(f"\n--- Updating memory {memory_id} ---")
        memory.update(memory_id, data="I love playing tennis and I'm working on improving my serve and backhand.")
        
        # Verify the update
        updated_memory = memory.get(memory_id)
        print(f"Updated memory: {updated_memory['memory']}")
    
    # Delete a memory
    if len(alice_memories['results']) > 1:
        memory_id = alice_memories['results'][1]['id']
        print(f"\n--- Deleting memory {memory_id} ---")
        memory.delete(memory_id)
        print("Memory deleted successfully!")
    
    print("\nDocumentDB example completed!")

if __name__ == "__main__":
    main()