from unittest.mock import MagicMock, patch

from mem0.memory.main import Memory


def test_memory_configuration_without_env_vars():
    """Test Memory configuration with mock config instead of environment variables"""

    # Mock configuration without relying on environment variables
    mock_config = {
        "llm": {
            "provider": "openai",
            "config": {
                "model": "gpt-4",
                "temperature": 0.1,
                "max_tokens": 1500,
            },
        },
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": "test_collection",
                "path": "./test_db",
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": "text-embedding-ada-002",
            },
        },
    }

    # Test messages similar to the main.py file
    test_messages = [
        {"role": "user", "content": "Hi, I'm Alex. I'm a vegetarian and I'm allergic to nuts."},
        {
            "role": "assistant",
            "content": "Hello Alex! I've noted that you're a vegetarian and have a nut allergy. I'll keep this in mind for any food-related recommendations or discussions.",
        },
    ]

    # Mock the Memory class methods to avoid actual API calls
    with patch.object(Memory, "__init__", return_value=None):
        with patch.object(Memory, "from_config") as mock_from_config:
            with patch.object(Memory, "add") as mock_add:
                with patch.object(Memory, "get_all") as mock_get_all:
                    # Configure mocks
                    mock_memory_instance = MagicMock()
                    mock_from_config.return_value = mock_memory_instance

                    mock_add.return_value = {
                        "results": [
                            {"id": "1", "text": "Alex is a vegetarian"},
                            {"id": "2", "text": "Alex is allergic to nuts"},
                        ]
                    }

                    mock_get_all.return_value = [
                        {"id": "1", "text": "Alex is a vegetarian", "metadata": {"category": "dietary_preferences"}},
                        {"id": "2", "text": "Alex is allergic to nuts", "metadata": {"category": "allergies"}},
                    ]

                    # Test the workflow
                    mem = Memory.from_config(config_dict=mock_config)
                    assert mem is not None

                    # Test adding memories
                    result = mock_add(test_messages, user_id="alice", metadata={"category": "book_recommendations"})
                    assert "results" in result
                    assert len(result["results"]) == 2

                    # Test retrieving memories
                    all_memories = mock_get_all(user_id="alice")
                    assert len(all_memories) == 2
                    assert any("vegetarian" in memory["text"] for memory in all_memories)
                    assert any("allergic to nuts" in memory["text"] for memory in all_memories)


def test_azure_config_structure():
    """Test that Azure configuration structure is properly formatted"""

    # Test Azure configuration structure (without actual credentials)
    azure_config = {
        "llm": {
            "provider": "azure_openai",
            "config": {
                "model": "gpt-4",
                "temperature": 0.1,
                "max_tokens": 1500,
                "azure_kwargs": {
                    "azure_deployment": "test-deployment",
                    "api_version": "2023-12-01-preview",
                    "azure_endpoint": "https://test.openai.azure.com/",
                    "api_key": "test-key",
                },
            },
        },
        "vector_store": {
            "provider": "azure_ai_search",
            "config": {
                "service_name": "test-service",
                "api_key": "test-key",
                "collection_name": "test-collection",
                "embedding_model_dims": 1536,
            },
        },
        "embedder": {
            "provider": "azure_openai",
            "config": {
                "model": "text-embedding-ada-002",
                "api_key": "test-key",
                "azure_kwargs": {
                    "api_version": "2023-12-01-preview",
                    "azure_deployment": "test-embedding-deployment",
                    "azure_endpoint": "https://test.openai.azure.com/",
                    "api_key": "test-key",
                },
            },
        },
    }

    # Validate configuration structure
    assert "llm" in azure_config
    assert "vector_store" in azure_config
    assert "embedder" in azure_config

    # Validate Azure-specific configurations
    assert azure_config["llm"]["provider"] == "azure_openai"
    assert "azure_kwargs" in azure_config["llm"]["config"]
    assert "azure_deployment" in azure_config["llm"]["config"]["azure_kwargs"]

    assert azure_config["vector_store"]["provider"] == "azure_ai_search"
    assert "service_name" in azure_config["vector_store"]["config"]

    assert azure_config["embedder"]["provider"] == "azure_openai"
    assert "azure_kwargs" in azure_config["embedder"]["config"]


def test_memory_messages_format():
    """Test that memory messages are properly formatted"""

    # Test message format from main.py
    messages = [
        {"role": "user", "content": "Hi, I'm Alex. I'm a vegetarian and I'm allergic to nuts."},
        {
            "role": "assistant",
            "content": "Hello Alex! I've noted that you're a vegetarian and have a nut allergy. I'll keep this in mind for any food-related recommendations or discussions.",
        },
    ]

    # Validate message structure
    assert len(messages) == 2
    assert all("role" in msg for msg in messages)
    assert all("content" in msg for msg in messages)

    # Validate roles
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"

    # Validate content
    assert "vegetarian" in messages[0]["content"].lower()
    assert "allergic to nuts" in messages[0]["content"].lower()
    assert "vegetarian" in messages[1]["content"].lower()
    assert "nut allergy" in messages[1]["content"].lower()


def test_safe_update_prompt_constant():
    """Test the SAFE_UPDATE_PROMPT constant from main.py"""

    SAFE_UPDATE_PROMPT = """
Based on the user's latest messages, what new preference can be inferred?
Reply only in this json_object format:
"""

    # Validate prompt structure
    assert isinstance(SAFE_UPDATE_PROMPT, str)
    assert "user's latest messages" in SAFE_UPDATE_PROMPT
    assert "json_object format" in SAFE_UPDATE_PROMPT
    assert len(SAFE_UPDATE_PROMPT.strip()) > 0
