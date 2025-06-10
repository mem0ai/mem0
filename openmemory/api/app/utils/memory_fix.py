"""
A utility module to help fix the Qdrant connection issue.
"""
import os
from app.utils.memory import Memory

def get_memory_client_fixed(custom_instructions: str = None):
    """
    Fixed version of get_memory_client that properly handles Qdrant Cloud URLs
    """
    try:
        # Check if QDRANT_URL is directly provided (preferred for Qdrant Cloud)
        qdrant_url = os.getenv("QDRANT_URL")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")
        collection_name = os.getenv("MAIN_QDRANT_COLLECTION_NAME")

        if not collection_name:
            raise ValueError("MAIN_QDRANT_COLLECTION_NAME must be set in .env for mem0 Qdrant config.")

        llm_provider = os.getenv("LLM_PROVIDER", "openai")
        openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        embedder_provider = os.getenv("EMBEDDER_PROVIDER", "openai")
        embedder_model = os.getenv("EMBEDDER_MODEL", "text-embedding-3-small")
        openai_api_key = os.getenv("OPENAI_API_KEY")

        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment variables for mem0.")

        # Build Qdrant config
        qdrant_config = {
            "collection_name": collection_name,
        }
        
        # If direct URL is provided, use it
        if qdrant_url:
            qdrant_config["url"] = qdrant_url
            if qdrant_api_key:
                qdrant_config["api_key"] = qdrant_api_key
        else:
            # Fall back to host/port format
            qdrant_host = os.getenv("QDRANT_HOST", "localhost")
            qdrant_port = int(os.getenv("QDRANT_PORT", 6333))
            qdrant_config["host"] = qdrant_host
            qdrant_config["port"] = qdrant_port
            if qdrant_api_key:
                qdrant_config["api_key"] = qdrant_api_key

        config = {
            "vector_store": {
                "provider": "qdrant",
                "config": qdrant_config
            },
            "llm": {
                "provider": llm_provider,
                "config": {
                    "model": openai_model,
                    "api_key": openai_api_key
                }
            },
            "embedder": {
                "provider": embedder_provider,
                "config": {
                    "model": embedder_model,
                    "api_key": openai_api_key
                }
            }
        }
        
        print(f"DEBUG: Initializing with Qdrant config: {qdrant_config}")
        memory_instance = Memory.from_config(config_dict=config)

    except Exception as e:
        print(f"ERROR: Error initializing memory client with collection '{collection_name}': {e}")
        raise Exception(f"Could not initialize memory client: {e}")
            
    return memory_instance
