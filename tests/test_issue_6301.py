from unittest.mock import patch

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.huggingface import HuggingFaceEmbedding


def test_issue_6301(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config = BaseEmbedderConfig(
        huggingface_base_url="http://localhost:8080",
        api_key="hf_myEndpointToken",
    )

    with patch("mem0.embeddings.huggingface.OpenAI") as mock_openai:
        HuggingFaceEmbedding(config)

    mock_openai.assert_called_once_with(
        base_url="http://localhost:8080",
        api_key="hf_myEndpointToken",
    )
