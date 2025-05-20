import os

from mem0 import Memory
from app.utils.anthropic_embeddings import anthropic_embedder
from app.utils.anthropic_llm import anthropic_llm

memory_client = None


def get_memory_client(custom_instructions: str = None):
    """
    Get or initialize the Mem0 client.

    Args:
        custom_instructions: Optional instructions for the memory project.

    Returns:
        Initialized Mem0 client instance.

    Raises:
        Exception: If required API keys are not set.
    """
    global memory_client

    if memory_client is not None:
        return memory_client

    try:
        config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "openmemory",
                    "host": "mem0_store",
                    "port": 6333,
                }
            }
        }

        memory_client = Memory.from_config(config_dict=config)
    except Exception:
        raise Exception("Exception occurred while initializing memory client")

    # Update project with custom instructions if provided
    if custom_instructions:
        memory_client.update_project(custom_instructions=custom_instructions)

    # Patch the embedding model if using Anthropic
    if config.get("embedding_model_provider") == "anthropic":
        # Replace the OpenAI embedding function with our Anthropic one
        memory_client.embedding_model.embed_documents = anthropic_embedder.embed_documents

    # Patch the LLM if using Anthropic
    if os.environ.get("LLM_PROVIDER") == "anthropic":
        memory_client.llm.generate_response = anthropic_llm.generate_response

    return memory_client


def get_default_user_id():
    return "default_user"
