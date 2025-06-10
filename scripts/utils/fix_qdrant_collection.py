#!/usr/bin/env python3
"""
Script to fix the Qdrant collection by adding the missing user_id index.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models

def load_env_file():
    """Load environment variables from .env file"""
    # Get the directory of this script
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    
    # Try to find the env file in the api directory
    env_path = script_dir / "openmemory" / "api" / ".env"
    
    if env_path.exists():
        print(f"Loading environment from {env_path}")
        load_dotenv(dotenv_path=env_path)
    else:
        # Try fallback locations
        fallback_paths = [
            script_dir / ".env",  # Root directory .env
        ]
        
        for path in fallback_paths:
            if path.exists():
                print(f"Loading environment from {path}")
                load_dotenv(dotenv_path=path)
                return
        
        print("Warning: No .env file found")

def main():
    # Load environment variables from .env file
    load_env_file()
    
    # Import config after loading env
    try:
        from openmemory.api.app.settings import config
        qdrant_host = config.QDRANT_HOST
        qdrant_port = config.QDRANT_PORT
        qdrant_api_key = config.QDRANT_API_KEY
        collection_name = config.QDRANT_COLLECTION_NAME
    except ImportError:
        # Fallback to direct env vars if config module not available
        qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
        qdrant_api_key = os.getenv("QDRANT_API_KEY", "")
        collection_name = os.getenv("MAIN_QDRANT_COLLECTION_NAME", "jonathans_memory_main")
    
    print(f"Connecting to Qdrant at {qdrant_host}:{qdrant_port} for collection {collection_name}")
    
    # Connect to Qdrant
    # For local development with Docker, we use http and localhost
    # For cloud deployment, we'd use https and the cloud host
    if qdrant_host == "localhost":
        # Local Docker setup
        print("Using local Qdrant setup")
        client = QdrantClient(host=qdrant_host, port=qdrant_port)
    else:
        # Cloud setup with API key
        print("Using cloud Qdrant setup")
        url = f"https://{qdrant_host}:{qdrant_port}"
        client = QdrantClient(url=url, api_key=qdrant_api_key)
    
    # Check if collection exists, if not create it
    collections = client.get_collections().collections
    collection_names = [collection.name for collection in collections]
    
    if collection_name not in collection_names:
        print(f"Collection {collection_name} does not exist, creating it...")
        try:
            # Create collection with OpenAI embeddings dimension (1536 for text-embedding-3-small)
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=1536,  # OpenAI text-embedding-3-small dimension
                    distance=models.Distance.COSINE,
                ),
            )
            print(f"Collection {collection_name} created successfully!")
        except Exception as e:
            print(f"Error creating collection: {e}")
    
    # Create payload index for user_id
    try:
        print(f"Creating payload index for 'user_id' field in collection {collection_name}")
        client.create_payload_index(
            collection_name=collection_name,
            field_name="user_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        print("Payload index created successfully!")
    except Exception as e:
        print(f"Error creating payload index: {e}")
        
    # Also try with UUID type as mentioned in the error
    try:
        print(f"Creating additional UUID payload index for 'user_id' field")
        client.create_payload_index(
            collection_name=collection_name,
            field_name="user_id",
            field_schema=models.PayloadSchemaType.UUID,  # Try UUID as mentioned in error
        )
        print("Additional payload index created successfully!")
    except Exception as e:
        print(f"Error creating additional payload index: {e}")
    
    # Verify collection info
    try:
        collection_info = client.get_collection(collection_name=collection_name)
        print(f"Collection info: {collection_info}")
    except Exception as e:
        print(f"Error getting collection info: {e}")

if __name__ == "__main__":
    main()
