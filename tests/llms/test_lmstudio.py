from unittest.mock import Mock, patch

import os

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.lmstudio import LMStudioConfig
from mem0.llms.lmstudio import LMStudioLLM


@pytest.fixture
def mock_openai():
    with patch("mem0.llms.lmstudio.OpenAI") as mock_cls:
        mock_cls.return_value = Mock()
        yield mock_cls


def test_lmstudio_honors_env_base_url(mock_openai, monkeypatch):
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://remote-lms:1234/v1")
    # BaseLlmConfig path (no provider-specific url set)
    LMStudioLLM(BaseLlmConfig(model="local-model"))
    assert mock_openai.call_args.kwargs["base_url"] == "http://remote-lms:1234/v1"


def test_lmstudio_config_overrides_env(mock_openai, monkeypatch):
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://env-host:1234/v1")
    LMStudioLLM(LMStudioConfig(model="local-model", lmstudio_base_url="http://cfg-host:1234/v1"))
    assert mock_openai.call_args.kwargs["base_url"] == "http://cfg-host:1234/v1"


def test_lmstudio_default_base_url(mock_openai, monkeypatch):
    monkeypatch.delenv("LMSTUDIO_BASE_URL", raising=False)
    LMStudioLLM(BaseLlmConfig(model="local-model"))
    assert mock_openai.call_args.kwargs["base_url"] == "http://localhost:1234/v1"
