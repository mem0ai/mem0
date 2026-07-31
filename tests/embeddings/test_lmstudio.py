from unittest.mock import patch

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.lmstudio import LMStudioEmbedding


def test_lmstudio_embedder_honors_explicit_base_url():
    with patch("mem0.embeddings.lmstudio.OpenAI") as mock_openai:
        LMStudioEmbedding(BaseEmbedderConfig(lmstudio_base_url="http://custom:9999/v1"))
        mock_openai.assert_called_once()
        assert mock_openai.call_args.kwargs["base_url"] == "http://custom:9999/v1"


def test_lmstudio_embedder_honors_env_when_config_unset(monkeypatch):
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://env-host:5555/v1")
    with patch("mem0.embeddings.lmstudio.OpenAI") as mock_openai:
        emb = LMStudioEmbedding(BaseEmbedderConfig())
        mock_openai.assert_called_once()
        assert mock_openai.call_args.kwargs["base_url"] == "http://env-host:5555/v1"
        assert emb.config.lmstudio_base_url == "http://env-host:5555/v1"


def test_lmstudio_embedder_default_localhost_when_no_env(monkeypatch):
    monkeypatch.delenv("LMSTUDIO_BASE_URL", raising=False)
    with patch("mem0.embeddings.lmstudio.OpenAI") as mock_openai:
        LMStudioEmbedding(BaseEmbedderConfig())
        assert mock_openai.call_args.kwargs["base_url"] == "http://localhost:1234/v1"


def test_lmstudio_embedder_explicit_config_beats_env(monkeypatch):
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://env-host:5555/v1")
    with patch("mem0.embeddings.lmstudio.OpenAI") as mock_openai:
        LMStudioEmbedding(BaseEmbedderConfig(lmstudio_base_url="http://config-host:1/v1"))
        assert mock_openai.call_args.kwargs["base_url"] == "http://config-host:1/v1"
