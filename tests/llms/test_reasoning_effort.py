"""
Tests for reasoning_effort parameter support across LLM configs and providers.
Covers: BaseLlmConfig, AzureOpenAIConfig, OpenAIConfig, LLMBase._get_supported_params,
        AzureOpenAILLM, and OpenAILLM.
"""

from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.azure import AzureOpenAIConfig
from mem0.configs.llms.openai import OpenAIConfig
from mem0.llms.azure_openai import AzureOpenAILLM
from mem0.llms.openai import OpenAILLM


# ─── Config Tests ────────────────────────────────────────────────────────────


class TestBaseLlmConfigReasoningEffort:
    def test_default_is_none(self):
        config = BaseLlmConfig()
        assert config.reasoning_effort is None

    def test_accepts_low(self):
        config = BaseLlmConfig(reasoning_effort="low")
        assert config.reasoning_effort == "low"

    def test_accepts_medium(self):
        config = BaseLlmConfig(reasoning_effort="medium")
        assert config.reasoning_effort == "medium"

    def test_accepts_high(self):
        config = BaseLlmConfig(reasoning_effort="high")
        assert config.reasoning_effort == "high"


class TestAzureOpenAIConfigReasoningEffort:
    def test_default_is_none(self):
        config = AzureOpenAIConfig()
        assert config.reasoning_effort is None

    def test_passes_to_super(self):
        config = AzureOpenAIConfig(model="o3-mini", reasoning_effort="low")
        assert config.reasoning_effort == "low"
        assert config.model == "o3-mini"

    def test_all_values(self):
        for value in ["low", "medium", "high"]:
            config = AzureOpenAIConfig(reasoning_effort=value)
            assert config.reasoning_effort == value


class TestOpenAIConfigReasoningEffort:
    def test_default_is_none(self):
        config = OpenAIConfig()
        assert config.reasoning_effort is None

    def test_passes_to_super(self):
        config = OpenAIConfig(model="o3-mini", reasoning_effort="low")
        assert config.reasoning_effort == "low"
        assert config.model == "o3-mini"

    def test_all_values(self):
        for value in ["low", "medium", "high"]:
            config = OpenAIConfig(reasoning_effort=value)
            assert config.reasoning_effort == value


# ─── LLMBase._get_supported_params Tests ─────────────────────────────────────


class TestGetSupportedParamsReasoningEffort:
    """Test that _get_supported_params correctly handles reasoning_effort for reasoning models."""

    def _make_llm(self, model, reasoning_effort=None):
        """Helper: create a concrete LLM subclass for testing base class logic."""

        class DummyLLM(OpenAILLM):
            pass

        with patch("mem0.llms.openai.OpenAI"):
            config = OpenAIConfig(
                model=model,
                reasoning_effort=reasoning_effort,
                api_key="test-key",
            )
            llm = DummyLLM(config)
        return llm

    def test_reasoning_model_includes_reasoning_effort(self):
        llm = self._make_llm("o3-mini", reasoning_effort="low")
        params = llm._get_supported_params(messages=[{"role": "user", "content": "hi"}])
        assert "reasoning_effort" in params
        assert params["reasoning_effort"] == "low"

    def test_reasoning_model_excludes_temperature(self):
        llm = self._make_llm("o3-mini", reasoning_effort="low")
        params = llm._get_supported_params(messages=[{"role": "user", "content": "hi"}])
        assert "temperature" not in params
        assert "max_tokens" not in params
        assert "top_p" not in params

    def test_reasoning_model_without_effort_omits_param(self):
        llm = self._make_llm("o3-mini", reasoning_effort=None)
        params = llm._get_supported_params(messages=[{"role": "user", "content": "hi"}])
        assert "reasoning_effort" not in params

    def test_regular_model_does_not_include_reasoning_effort(self):
        llm = self._make_llm("gpt-4.1-nano-2025-04-14", reasoning_effort="low")
        params = llm._get_supported_params(messages=[{"role": "user", "content": "hi"}])
        # Regular models use _get_common_params, which doesn't inject reasoning_effort
        assert "temperature" in params
        assert "max_tokens" in params

    @pytest.mark.parametrize("model", ["o1", "o1-preview", "o3-mini", "o3", "gpt-5"])
    def test_various_reasoning_models(self, model):
        llm = self._make_llm(model, reasoning_effort="medium")
        params = llm._get_supported_params(messages=[{"role": "user", "content": "hi"}])
        assert params["reasoning_effort"] == "medium"

    def test_reasoning_model_preserves_tools(self):
        llm = self._make_llm("o3-mini", reasoning_effort="high")
        tools = [{"type": "function", "function": {"name": "test"}}]
        params = llm._get_supported_params(
            messages=[{"role": "user", "content": "hi"}],
            tools=tools,
            tool_choice="auto",
        )
        assert params["tools"] == tools
        assert params["tool_choice"] == "auto"
        assert params["reasoning_effort"] == "high"


# ─── End-to-End: AzureOpenAILLM ──────────────────────────────────────────────


class TestAzureOpenAILLMReasoningEffort:
    @pytest.fixture
    def mock_azure_client(self):
        with patch("mem0.llms.azure_openai.AzureOpenAI") as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            yield mock_client

    def test_reasoning_effort_sent_to_api(self, mock_azure_client):
        config = AzureOpenAIConfig(
            model="o3-mini",
            reasoning_effort="low",
            api_key="test-key",
        )
        llm = AzureOpenAILLM(config)

        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Solve this math problem."},
        ]

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="The answer is 42."))]
        mock_azure_client.chat.completions.create.return_value = mock_response

        response = llm.generate_response(messages)

        # Verify reasoning_effort was passed in the API call
        call_kwargs = mock_azure_client.chat.completions.create.call_args
        assert call_kwargs[1].get("reasoning_effort") == "low" or \
               call_kwargs.kwargs.get("reasoning_effort") == "low"

        # Verify temperature/max_tokens/top_p are NOT sent for reasoning models
        all_args = {**call_kwargs.kwargs} if call_kwargs.kwargs else dict(zip([], []))
        if call_kwargs[1]:
            all_args.update(call_kwargs[1])
        assert "temperature" not in all_args
        assert "top_p" not in all_args

        assert response == "The answer is 42."

    def test_no_reasoning_effort_for_regular_model(self, mock_azure_client):
        config = AzureOpenAIConfig(
            model="gpt-4.1-nano-2025-04-14",
            temperature=0.7,
            max_tokens=100,
            top_p=1.0,
            api_key="test-key",
        )
        llm = AzureOpenAILLM(config)

        messages = [{"role": "user", "content": "Hello"}]

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Hi!"))]
        mock_azure_client.chat.completions.create.return_value = mock_response

        llm.generate_response(messages)

        call_kwargs = mock_azure_client.chat.completions.create.call_args
        # For regular models, reasoning_effort should NOT be present
        all_kwargs = call_kwargs[1] if call_kwargs[1] else call_kwargs.kwargs
        assert "reasoning_effort" not in all_kwargs

    def test_config_conversion_preserves_reasoning_effort(self, mock_azure_client):
        """When BaseLlmConfig is passed, reasoning_effort should survive conversion."""
        base_config = BaseLlmConfig(
            model="o3-mini",
            reasoning_effort="medium",
            api_key="test-key",
        )
        llm = AzureOpenAILLM(base_config)
        assert llm.config.reasoning_effort == "medium"


# ─── End-to-End: OpenAILLM ───────────────────────────────────────────────────


class TestOpenAILLMReasoningEffort:
    @pytest.fixture
    def mock_openai_client(self):
        with patch("mem0.llms.openai.OpenAI") as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            yield mock_client

    def test_reasoning_effort_sent_to_api(self, mock_openai_client):
        config = OpenAIConfig(
            model="o3-mini",
            reasoning_effort="low",
            api_key="test-key",
        )
        llm = OpenAILLM(config)

        messages = [
            {"role": "user", "content": "Think step by step about this problem."},
        ]

        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Step 1..."))]
        mock_openai_client.chat.completions.create.return_value = mock_response

        response = llm.generate_response(messages)

        call_kwargs = mock_openai_client.chat.completions.create.call_args
        all_kwargs = call_kwargs[1] if call_kwargs[1] else call_kwargs.kwargs
        assert all_kwargs.get("reasoning_effort") == "low"
        assert response == "Step 1..."

    def test_config_conversion_preserves_reasoning_effort(self, mock_openai_client):
        """When BaseLlmConfig is passed, reasoning_effort should survive conversion."""
        base_config = BaseLlmConfig(
            model="o3-mini",
            reasoning_effort="high",
            api_key="test-key",
        )
        llm = OpenAILLM(base_config)
        assert llm.config.reasoning_effort == "high"
