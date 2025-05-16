import os

from mem0 import Memory


def get_memory_client(custom_instructions: str = None):
    """
    Initializes and returns a Mem0 client configured with a static Qdrant collection.
    User-specific operations will be handled by passing user_id to the mem0 client's methods.
    """
    try:
        qdrant_host = os.getenv("QDRANT_HOST", "mem0_store")
        qdrant_port = int(os.getenv("QDRANT_PORT", 6333))
        collection_name = os.getenv("MAIN_QDRANT_COLLECTION_NAME")

        if not collection_name:
            raise ValueError("MAIN_QDRANT_COLLECTION_NAME must be set in .env for mem0 Qdrant config.")

        llm_provider = os.getenv("LLM_PROVIDER", "openai")
        openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        embedder_provider = os.getenv("EMBEDDER_PROVIDER", "openai")
        embedder_model = os.getenv("EMBEDDER_MODEL", "text-embedding-ada-002")
        openai_api_key = os.getenv("OPENAI_API_KEY")

        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY must be set in environment variables for mem0.")

        config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": collection_name,
                    "host": qdrant_host,
                    "port": qdrant_port,
                    # Add "api_key": os.getenv("QDRANT_API_KEY") if using Qdrant Cloud and it needs an API key
                }
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
        # For debugging initialization:
        # print(f"Initializing mem0 client. Qdrant: host='{qdrant_host}', port={qdrant_port}, collection='{collection_name}'")
        # print(f"LLM: provider='{llm_provider}', model='{openai_model}'")
        # print(f"Embedder: provider='{embedder_provider}', model='{embedder_model}'")

        memory_instance = Memory.from_config(config_dict=config)

    except Exception as e:
        print(f"ERROR: Error initializing memory client with collection '{collection_name}': {e}") # Enhanced logging
        # Consider more specific error handling or re-raising with context
        raise Exception(f"Could not initialize memory client: {e}")

    # The .update_project() method might apply to the client's general behavior.
    # If custom_instructions are global, this is fine. If they were meant to be per-user,
    # this approach needs reconsideration for custom_instructions. For MVP, defer if complex.
    # if custom_instructions:
    #     try:
    #         memory_instance.update_project(custom_instructions=custom_instructions)
    #     except Exception as e:
    #         print(f"Warning: Failed to update project with custom instructions: {e}")
            
    return memory_instance
