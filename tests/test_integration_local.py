import pytest
import os
from mem0 import Memory
from mem0.configs.base import MemoryConfig

from unittest.mock import patch, MagicMock

# Skip test if dependencies are missing
try:
    import sentence_transformers
    import qdrant_client
    DEPENDENCIES_INSTALLED = True
except ImportError:
    DEPENDENCIES_INSTALLED = False

@pytest.fixture
def local_memory():
    """
    Fixture for a fully local Memory instance:
    - Embedding: HuggingFace (sentence-transformers/all-MiniLM-L6-v2)
    - Vector Store: Qdrant (:memory:)
    - LLM: Mocked (to avoid API key requirements)
    """
    with patch("mem0.memory.main.LlmFactory.create") as mock_llm:
        # Configuration
        config = MemoryConfig(
            embedder={
                "provider": "huggingface",
                "config": {
                    "model": "sentence-transformers/all-MiniLM-L6-v2"
                }
            },
            vector_store={
                "provider": "qdrant",
                "config": {
                    "collection_name": "test_integration_local",
                    "path": ":memory:",
                    "embedding_model_dims": 384,
                }
            },
            history_db_path=":memory:"
        )
        
        # Setup Mock LLM behavior if needed (for infer=True)
        # For this basic integration test, we might use infer=False or expect the mock to be called
        mock_llm_instance = MagicMock()
        mock_llm.return_value = mock_llm_instance
        
        yield Memory(config=config)

@pytest.mark.skipif(not DEPENDENCIES_INSTALLED, reason="sentence-transformers or qdrant-client not installed")
def test_full_lifecycle(local_memory):
    """
    Test the full lifecycle of a memory:
    1. Add
    2. Search
    3. Get
    4. Update
    5. Delete
    """
    user_id = "test_user_integration"
    memory_text = "I am writing an integration test for mem0."
    
    # 1. Add
    print("\n[TEST] Adding memory...")
    add_response = local_memory.add(
        messages=[{"role": "user", "content": memory_text}],
        user_id=user_id,
        infer=False
    )
    assert len(add_response["results"]) > 0
    memory_id = add_response["results"][0]["id"]
    print(f"[TEST] Added memory ID: {memory_id}")

    # 2. Search
    print("[TEST] Searching memory...")
    search_response = local_memory.search("integration test", user_id=user_id)
    assert len(search_response["results"]) > 0
    found_memory = search_response["results"][0]
    assert found_memory["memory"] == memory_text
    print("[TEST] Search successful.")

    # 3. Get
    print("[TEST] Getting memory by ID...")
    get_response = local_memory.get(memory_id)
    assert get_response["memory"] == memory_text
    print("[TEST] Get successful.")

    # 4. Update
    print("[TEST] Updating memory...")
    new_text = "I have updated this memory locally."
    update_response = local_memory.update(memory_id, data=new_text)
    assert "updated" in update_response["message"].lower()

    # Verify update
    get_updated = local_memory.get(memory_id)
    assert get_updated["memory"] == new_text
    print("[TEST] Update successful.")

    # 5. History
    print("[TEST] Checking history...")
    history = local_memory.history(memory_id)
    assert len(history) >= 2 # Add + Update
    assert history[0]["event"] == "ADD"
    assert history[-1]["event"] == "UPDATE"
    print("[TEST] History check successful.")

    # 6. Delete
    print("[TEST] Deleting memory...")
    delete_response = local_memory.delete(memory_id)
    assert "deleted" in delete_response["message"].lower()
    
    # Verify deletion
    get_deleted = local_memory.get(memory_id)
    # Qdrant behavior: might return None or raise error depending on implementation
    # Based on base implementation, it usually returns None or error, but let's check basic get_all
    all_memories = local_memory.get_all(user_id=user_id)
    # Validating it's gone from the user's list
    assert not any(m["id"] == memory_id for m in all_memories.get("results", []))
    print("[TEST] Delete successful.")
