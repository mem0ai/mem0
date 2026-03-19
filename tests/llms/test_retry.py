from unittest.mock import MagicMock, Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.base import LLMBase


class ConcreteLLM(LLMBase):
    """Concrete implementation for testing the base class retry logic."""

    def __init__(self, config=None):
        super().__init__(config)
        self.client = MagicMock()

    def generate_response(self, messages, tools=None, tool_choice="auto", **kwargs):
        return self._retry_with_backoff(self.client.chat.completions.create, messages=messages)


class TestRetryWithBackoff:
    def test_succeeds_on_first_try(self):
        config = BaseLlmConfig(model="test-model", max_retries=3, retry_delay=0.01)
        llm = ConcreteLLM(config)
        llm.client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="Hello!"))]
        )

        result = llm.generate_response([{"role": "user", "content": "Hi"}])
        assert result.choices[0].message.content == "Hello!"
        assert llm.client.chat.completions.create.call_count == 1

    def test_retries_on_rate_limit_error(self):
        config = BaseLlmConfig(model="test-model", max_retries=2, retry_delay=0.01)
        llm = ConcreteLLM(config)

        rate_limit_error = type("RateLimitError", (Exception,), {})()
        success_response = Mock(choices=[Mock(message=Mock(content="Success after retry"))])
        llm.client.chat.completions.create.side_effect = [rate_limit_error, success_response]

        result = llm.generate_response([{"role": "user", "content": "Hi"}])
        assert result.choices[0].message.content == "Success after retry"
        assert llm.client.chat.completions.create.call_count == 2

    def test_retries_on_server_error(self):
        config = BaseLlmConfig(model="test-model", max_retries=2, retry_delay=0.01)
        llm = ConcreteLLM(config)

        server_error = Exception("server error")
        server_error.status_code = 500
        success_response = Mock(choices=[Mock(message=Mock(content="Recovered"))])
        llm.client.chat.completions.create.side_effect = [server_error, success_response]

        result = llm.generate_response([{"role": "user", "content": "Hi"}])
        assert result.choices[0].message.content == "Recovered"
        assert llm.client.chat.completions.create.call_count == 2

    def test_retries_on_timeout(self):
        config = BaseLlmConfig(model="test-model", max_retries=2, retry_delay=0.01)
        llm = ConcreteLLM(config)

        timeout_error = type("APITimeoutError", (Exception,), {})()
        success_response = Mock(choices=[Mock(message=Mock(content="Recovered"))])
        llm.client.chat.completions.create.side_effect = [timeout_error, success_response]

        result = llm.generate_response([{"role": "user", "content": "Hi"}])
        assert result.choices[0].message.content == "Recovered"

    def test_does_not_retry_on_auth_error(self):
        config = BaseLlmConfig(model="test-model", max_retries=3, retry_delay=0.01)
        llm = ConcreteLLM(config)

        auth_error = Exception("Invalid API key")
        auth_error.status_code = 401
        llm.client.chat.completions.create.side_effect = auth_error

        with pytest.raises(Exception, match="Invalid API key"):
            llm.generate_response([{"role": "user", "content": "Hi"}])
        assert llm.client.chat.completions.create.call_count == 1

    def test_raises_after_max_retries_exhausted(self):
        config = BaseLlmConfig(model="test-model", max_retries=2, retry_delay=0.01)
        llm = ConcreteLLM(config)

        rate_limit_error = type("RateLimitError", (Exception,), {})()
        llm.client.chat.completions.create.side_effect = rate_limit_error

        with pytest.raises(Exception):
            llm.generate_response([{"role": "user", "content": "Hi"}])
        # 1 initial + 2 retries = 3 total calls
        assert llm.client.chat.completions.create.call_count == 3

    def test_retries_disabled_when_max_retries_zero(self):
        config = BaseLlmConfig(model="test-model", max_retries=0, retry_delay=0.01)
        llm = ConcreteLLM(config)

        rate_limit_error = type("RateLimitError", (Exception,), {})()
        llm.client.chat.completions.create.side_effect = rate_limit_error

        with pytest.raises(Exception):
            llm.generate_response([{"role": "user", "content": "Hi"}])
        assert llm.client.chat.completions.create.call_count == 1

    def test_retry_config_defaults(self):
        config = BaseLlmConfig(model="test-model")
        assert config.max_retries == 3
        assert config.retry_delay == 1.0

    def test_retries_on_connection_error(self):
        config = BaseLlmConfig(model="test-model", max_retries=1, retry_delay=0.01)
        llm = ConcreteLLM(config)

        connection_error = type("APIConnectionError", (Exception,), {})()
        success_response = Mock(choices=[Mock(message=Mock(content="Recovered"))])
        llm.client.chat.completions.create.side_effect = [connection_error, success_response]

        result = llm.generate_response([{"role": "user", "content": "Hi"}])
        assert result.choices[0].message.content == "Recovered"

    def test_retries_on_429_status_code(self):
        config = BaseLlmConfig(model="test-model", max_retries=1, retry_delay=0.01)
        llm = ConcreteLLM(config)

        error_429 = Exception("Too many requests")
        error_429.status_code = 429
        success_response = Mock(choices=[Mock(message=Mock(content="OK"))])
        llm.client.chat.completions.create.side_effect = [error_429, success_response]

        result = llm.generate_response([{"role": "user", "content": "Hi"}])
        assert result.choices[0].message.content == "OK"
