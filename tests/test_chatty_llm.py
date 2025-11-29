
import pytest
from unittest.mock import MagicMock
import json
from mem0 import Memory, AsyncMemory

# Chatty response simulating local LLMs (Ollama/LM Studio)
CHATTY_RESPONSE = """
Here is the extracted memory:
```json
{
  "memory": [
    {
      "id": "0",
      "text": "User likes basketball",
      "event": "ADD"
    }
  ]
}
```
I hope this helps!
"""

# Response without markdown but with JSON
CHATTY_NO_MARKDOWN_RESPONSE = """
Here is the memory update you requested:
{
  "memory": [
    {
      "id": "0",
      "text": "User likes gaming",
      "event": "ADD"
    }
  ]
}
"""

SIMPLE_FACTS_BASKETBALL = '{"facts": ["User likes basketball"]}'
SIMPLE_FACTS_GAMING = '{"facts": ["User likes gaming"]}'

class MockLLM:
    def __init__(self, config=None):
        self.call_count = 0

    def generate_response(self, messages, response_format=None, **kwargs):
        self.call_count += 1
        content = str(messages)

        # Check if this is the gaming test case
        is_gaming = "gaming" in content.lower()

        # Step 1: Fact extraction (prompt usually asks to extract facts)
        if "facts" in content.lower() and "memory" not in content.lower():
             return SIMPLE_FACTS_GAMING if is_gaming else SIMPLE_FACTS_BASKETBALL

        # Step 2: Memory update action
        # If the input contains "gaming" (which comes from the facts in Step 1), return the no-markdown response
        if is_gaming:
            return CHATTY_NO_MARKDOWN_RESPONSE

        # Default to standard chatty markdown response
        return CHATTY_RESPONSE

class MockConfig:
    def __init__(self, d):
        for k, v in d.items():
            setattr(self, k, v)

class MockEmbedder:
    def __init__(self, config=None):
        if isinstance(config, dict):
             if 'embedding_dims' not in config:
                  config['embedding_dims'] = 1024
             self.config = MockConfig(config)
        else:
             if not hasattr(config, 'embedding_dims'):
                  config.embedding_dims = 1024
             self.config = config

    def embed(self, text, memory_action=None):
        return [0.1] * 1024

@pytest.fixture
def mock_components(monkeypatch):
    from mem0.utils import factory

    monkeypatch.setattr(factory.LlmFactory, "create", lambda p, c: MockLLM(c))
    monkeypatch.setattr(factory.EmbedderFactory, "create", lambda p, c, vc: MockEmbedder(c))
    # Mock VectorStore to avoid DB connection
    mock_vs = MagicMock()
    mock_vs.list.return_value = [] # No existing memories
    mock_vs.search.return_value = []
    monkeypatch.setattr(factory.VectorStoreFactory, "create", lambda p, c: mock_vs)

    return mock_vs

def test_chatty_llm_response_sync(mock_components):
    """Test that Memory handles chatty LLM responses (markdown) correctly."""
    config = {
        "vector_store": {
            "provider": "valkey",
            "config": {"collection_name": "test", "valkey_url": "valkey://localhost", "embedding_model_dims": 1024}
        },
        "llm": {"provider": "lmstudio", "config": {}},
        "embedder": {"provider": "ollama", "config": {"embedding_dims": 1024}}
    }

    m = Memory.from_config(config)
    m.db = MagicMock() # Mock history DB

    # Add memory
    results = m.add("I like basketball", user_id="test_user")

    # Verify extraction
    assert results is not None
    assert "results" in results
    assert len(results["results"]) == 1
    assert results["results"][0]["memory"] == "User likes basketball"
    assert results["results"][0]["event"] == "ADD"

def test_chatty_no_markdown_response_sync(mock_components):
    """Test that Memory handles chatty LLM responses (no markdown) correctly."""
    config = {
        "vector_store": {
            "provider": "valkey",
            "config": {"collection_name": "test", "valkey_url": "valkey://localhost", "embedding_model_dims": 1024}
        },
        "llm": {"provider": "lmstudio", "config": {}},
        "embedder": {"provider": "ollama", "config": {"embedding_dims": 1024}}
    }

    m = Memory.from_config(config)
    m.db = MagicMock() # Mock history DB

    # Add memory with keyword triggering no-markdown response in MockLLM
    results = m.add("I like gaming", user_id="test_user")

    # Verify extraction
    assert results is not None
    assert "results" in results
    assert len(results["results"]) == 1
    assert results["results"][0]["memory"] == "User likes gaming"
    assert results["results"][0]["event"] == "ADD"

@pytest.mark.asyncio
async def test_chatty_llm_response_async(mock_components):
    """Test that AsyncMemory handles chatty LLM responses correctly."""
    config = {
        "vector_store": {
            "provider": "valkey",
            "config": {"collection_name": "test", "valkey_url": "valkey://localhost", "embedding_model_dims": 1024}
        },
        "llm": {"provider": "lmstudio", "config": {}},
        "embedder": {"provider": "ollama", "config": {"embedding_dims": 1024}}
    }

    m = await AsyncMemory.from_config(config)
    m.db = MagicMock() # Mock history DB

    # Add memory
    results = await m.add("I like basketball", user_id="test_user")

    # Verify extraction
    assert results is not None
    assert "results" in results
    assert len(results["results"]) == 1
    assert results["results"][0]["memory"] == "User likes basketball"
    assert results["results"][0]["event"] == "ADD"
