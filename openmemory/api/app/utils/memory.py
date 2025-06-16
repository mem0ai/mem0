import os
from mem0 import Memory
from app.settings import config  # Import the application config


def get_memory_client(custom_instructions: str = None):
    """
    Initializes and returns a Mem0 client configured for the correct environment.
    """
    try:
        if config.is_local_development:
            qdrant_host = "localhost"
            qdrant_api_key = None # Force no API key for local dev
        else:
            qdrant_host = os.getenv("QDRANT_HOST")
            qdrant_api_key = os.getenv("QDRANT_API_KEY")

        qdrant_port = int(os.getenv("QDRANT_PORT", 6333))
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

        # Build Qdrant config with proper parameters for metadata support
        qdrant_config = {
            "collection_name": collection_name,
            "embedding_model_dims": 1536,  # Required for proper vector storage
        }
        
        # For Qdrant Cloud, use the full URL approach
        if qdrant_host and "cloud.qdrant.io" in qdrant_host:
            qdrant_config["url"] = f"https://{qdrant_host}:{qdrant_port}"
            if qdrant_api_key:
                qdrant_config["api_key"] = qdrant_api_key
        else:
            # Use host/port for local Qdrant
            qdrant_config["host"] = qdrant_host
            qdrant_config["port"] = qdrant_port
            if qdrant_api_key:
                qdrant_config["api_key"] = qdrant_api_key
        
        mem0_config = {
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
            },
            "version": "v1.1"  # Required for latest features including metadata support
        }

        memory_instance = Memory.from_config(config_dict=mem0_config)

    except Exception as e:
        # Enhanced logging
        print(f"ERROR: Error initializing memory client with collection '{collection_name}': {e}")
        raise Exception(f"Could not initialize memory client: {e}")
            
    return memory_instance
