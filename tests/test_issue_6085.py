import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

mem0_package = ModuleType("mem0")
mem0_package.__path__ = [str(Path(__file__).resolve().parents[1] / "mem0")]
sys.modules.setdefault("mem0", mem0_package)

from mem0.configs.llms.openai import OpenAIConfig
from mem0.llms.openai import OpenAILLM


def test_issue_6085():
    """Default OSS OpenAI config must not send temperature to gpt-5-mini."""
    with patch("mem0.llms.openai.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client

        config = OpenAIConfig()
        assert config.model is None
        assert config.temperature == 0.1
        assert config.is_reasoning_model is None

        llm = OpenAILLM(config)
        assert llm.config.model == "gpt-5-mini"

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="[]"))]
        mock_client.chat.completions.create.return_value = mock_response

        llm.generate_response([{"role": "user", "content": "Alice prefers window seats"}])

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-5-mini"
        assert "temperature" not in call_kwargs
