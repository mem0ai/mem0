from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_llm():
    with patch("mem0.reranker.llm_reranker.LlmFactory") as mock_factory:
        mock_llm_instance = MagicMock()
        mock_factory.create.return_value = mock_llm_instance
        yield mock_factory, mock_llm_instance
