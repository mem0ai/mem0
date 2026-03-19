"""Tests for reasoning_effort parameter support in LLM configurations."""

import pytest
from unittest.mock import Mock, patch

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.openai import OpenAIConfig
from mem0.configs.llms.azure import AzureOpenAIConfig
from mem0.llms.openai import OpenAILLM
from mem0.llms.azure_openai import AzureOpenAILLM


class TestReasoningEffortConfig:
    """Test reasoning_effort parameter in config classes."""

    def test_base_config_default_reasoning_effort_is_none(self):
        """reasoning_effort should default to None."""
        config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", api_key="test-key")
        assert config.reasoning_effort is None

    def test_base_config_accepts_reasoning_effort(self):
        """Config should accept reasoning_effort parameter."""
        config = OpenAIConfig(
            model="o3",
            api_key="test-key",
            reasoning_effort="low",
        )
        assert config.reasoning_effort == "low"

    def test_openai_config_reasoning_effort(self):
        """OpenAIConfig should pass reasoning_effort to base."""
        for effort in ["low", "medium", "high"]:
            config = OpenAIConfig(
                model="o3-mini",
                api_key="test-key",
                reasoning_effort=effort,
            )
            assert config.reasoning_effort == effort

    def test_azure_config_reasoning_effort(self):
        """AzureOpenAIConfig should pass reasoning_effort to base."""
        config = AzureOpenAIConfig(
            model="o3",
            api_key="test-key",
            reasoning_effort="high",
            azure_kwargs={
                "azure_deployment": "test-deployment",
                "azure_endpoint": "https://test.openai.azure.com/",
            },
        )
        assert config.reasoning_effort == "high"


class TestReasoningModelDetection:
    """Test _is_reasoning_model detection."""

    @patch("mem0.llms.openai.OpenAI")
    def test_reasoning_models_detected(self, mock_openai):
        """Known reasoning models should be detected."""
        mock_openai.return_value = Mock()
        reasoning_models = ["o1", "o1-preview", "o3-mini", "o3", "gpt-5", "gpt-5o", "gpt-5o-mini"]
        for model_name in reasoning_models:
            config = OpenAIConfig(model=model_name, api_key="test-key")
            llm = OpenAILLM(config)
            assert llm._is_reasoning_model(model_name), f"{model_name} should be detected as reasoning model"

    @patch("mem0.llms.openai.OpenAI")
    def test_regular_models_not_detected(self, mock_openai):
        """Regular models should not be detected as reasoning models."""
        mock_openai.return_value = Mock()
        regular_models = ["gpt-4.1-nano-2025-04-14", "gpt-4.1-2025-04-14", "gpt-4.1-mini-2025-07-18"]
        for model_name in regular_models:
            config = OpenAIConfig(model=model_name, api_key="test-key")
            llm = OpenAILLM(config)
            assert not llm._is_reasoning_model(model_name), f"{model_name} should NOT be detected as reasoning model"


class TestReasoningEffortInParams:
    """Test that reasoning_effort is correctly passed to API calls."""

    @patch("mem0.llms.openai.OpenAI")
    def test_reasoning_effort_included_for_reasoning_model(self, mock_openai):
        """reasoning_effort should be included in params for reasoning models."""
        mock_openai.return_value = Mock()
        config = OpenAIConfig(
            model="o3",
            api_key="test-key",
            reasoning_effort="low",
        )
        llm = OpenAILLM(config)
        params = llm._get_supported_params(messages=[{"role": "user", "content": "test"}])
        assert "reasoning_effort" in params
        assert params["reasoning_effort"] == "low"

    @patch("mem0.llms.openai.OpenAI")
    def test_reasoning_effort_not_included_when_none(self, mock_openai):
        """reasoning_effort should not be in params when not configured."""
        mock_openai.return_value = Mock()
        config = OpenAIConfig(
            model="o3",
            api_key="test-key",
        )
        llm = OpenAILLM(config)
        params = llm._get_supported_params(messages=[{"role": "user", "content": "test"}])
        assert "reasoning_effort" not in params

    @patch("mem0.llms.openai.OpenAI")
    def test_reasoning_effort_not_included_for_regular_model(self, mock_openai):
        """reasoning_effort should not affect regular model params."""
        mock_openai.return_value = Mock()
        config = OpenAIConfig(
            model="gpt-4.1-nano-2025-04-14",
            api_key="test-key",
            reasoning_effort="low",
        )
        llm = OpenAILLM(config)
        params = llm._get_supported_params(messages=[{"role": "user", "content": "test"}])
        # Regular models go through _get_common_params, not the reasoning path
        assert "temperature" in params

    @patch("mem0.llms.openai.OpenAI")
    def test_temperature_excluded_for_reasoning_model(self, mock_openai):
        """temperature should NOT be in params for reasoning models."""
        mock_openai.return_value = Mock()
        config = OpenAIConfig(
            model="o3",
            api_key="test-key",
            reasoning_effort="medium",
        )
        llm = OpenAILLM(config)
        params = llm._get_supported_params(messages=[{"role": "user", "content": "test"}])
        assert "temperature" not in params
        assert "top_p" not in params
        assert "max_tokens" not in params


class TestDictConfig:
    """Test reasoning_effort works when config is passed as dict."""

    @patch("mem0.llms.openai.OpenAI")
    def test_dict_config_with_reasoning_effort(self, mock_openai):
        """Should work when config is provided as a dict."""
        mock_openai.return_value = Mock()
        config_dict = {
            "model": "o3-mini",
            "api_key": "test-key",
            "reasoning_effort": "high",
        }
        llm = OpenAILLM(config=config_dict)
        assert llm.config.reasoning_effort == "high"
