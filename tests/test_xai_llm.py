from unittest.mock import Mock, patch

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.xai import XAILLM


def test_xai_base_url_defaults_to_env_or_fallback(monkeypatch):
    monkeypatch.delenv("XAI_API_BASE", raising=False)

    with patch("mem0.llms.xai.OpenAI") as mock_openai:
        mock_openai.return_value = Mock()
        XAILLM(BaseLlmConfig(api_key="test-key", model="grok-2-latest"))

        _, kwargs = mock_openai.call_args
        assert kwargs["base_url"] == "https://api.x.ai/v1"
