import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from mem0.configs.rerankers.cohere import CohereRerankerConfig
from mem0.reranker.cohere_reranker import CohereReranker


@pytest.fixture
def mock_cohere(monkeypatch):
    """Provide a fake cohere module so CohereReranker can construct without the SDK."""
    fake_cohere = ModuleType("cohere")
    fake_client = MagicMock()
    fake_cohere.Client = MagicMock(return_value=fake_client)
    monkeypatch.setitem(sys.modules, "cohere", fake_cohere)

    import mem0.reranker.cohere_reranker as cohere_reranker

    monkeypatch.setattr(cohere_reranker, "cohere", fake_cohere, raising=False)
    monkeypatch.setattr(cohere_reranker, "COHERE_AVAILABLE", True, raising=False)
    return cohere_reranker


def test_init_raises_when_api_key_missing(mock_cohere, monkeypatch):
    """Cohere reranker requires an API key via config or COHERE_API_KEY env var."""
    monkeypatch.delenv("COHERE_API_KEY", raising=False)
    config = CohereRerankerConfig(api_key=None)

    with pytest.raises(
        ValueError,
        match="Cohere API key is required. Set COHERE_API_KEY environment variable or pass api_key in config.",
    ):
        CohereReranker(config)