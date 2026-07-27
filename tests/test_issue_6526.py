"""Regression test for LM Studio base URL environment configuration."""

from unittest.mock import patch

from mem0.configs.llms.lmstudio import LMStudioConfig
from mem0.llms.lmstudio import LMStudioLLM


def test_issue_6526(monkeypatch):
    lmstudio_base_url = "http://lmstudio.example.test/v1"
    monkeypatch.setenv("LMSTUDIO_BASE_URL", lmstudio_base_url)

    with patch("mem0.llms.lmstudio.OpenAI") as mock_openai:
        LMStudioLLM(LMStudioConfig())

    assert mock_openai.call_args.kwargs["base_url"] == lmstudio_base_url
