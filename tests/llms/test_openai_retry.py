"""Tests for opt-in retry/backoff on the OpenAI LLM provider call path.

Retries are opt-in (``max_retries`` defaults to 0 → current behavior). When
enabled, transient OpenAI SDK errors are retried with backoff; on final failure
they are surfaced as mem0 typed exceptions. Non-transient errors (auth) are
never retried. ``time.sleep`` is patched so tests are fast and deterministic.
"""

from unittest.mock import Mock, patch

import httpx
import openai
import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.openai import OpenAIConfig
from mem0.exceptions import LLMError, NetworkError, RateLimitError
from mem0.llms.openai import OpenAILLM, _openai_retry_after


@pytest.fixture
def mock_openai_client():
    with patch("mem0.llms.openai.OpenAI") as mock_openai:
        client = Mock()
        mock_openai.return_value = client
        yield client


def _req():
    return httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


def _ok():
    response = Mock()
    response.choices = [Mock(message=Mock(content="ok"))]
    return response


def _rate_limit_error(retry_after=None):
    headers = {"retry-after": str(retry_after)} if retry_after is not None else {}
    resp = httpx.Response(429, request=_req(), headers=headers)
    return openai.RateLimitError("rate limited", response=resp, body=None)


def _timeout_error():
    return openai.APITimeoutError(request=_req())


def _auth_error():
    resp = httpx.Response(401, request=_req())
    return openai.AuthenticationError("bad key", response=resp, body=None)


def test_max_retries_defaults_to_zero_opt_in():
    assert BaseLlmConfig().max_retries == 0
    assert OpenAIConfig().max_retries == 0


def test_openai_base_url_positional_slot_preserved():
    """Regression: adding ``max_retries`` must not shift the historical positional
    slots of OpenAI-specific parameters.

    Before retries were introduced, ``openai_base_url`` was the 12th positional
    argument. A pre-existing positional call that passed the base URL in that slot
    must still bind it to ``openai_base_url`` (and leave ``max_retries`` at its
    default 0), not silently rebind the URL string to ``max_retries``.
    """
    base_url = "https://proxy.internal/v1"
    config = OpenAIConfig(
        "gpt-4.1-nano-2025-04-14",  # model
        0.1,  # temperature
        "api_key",  # api_key
        2000,  # max_tokens
        0.1,  # top_p
        1,  # top_k
        False,  # enable_vision
        "auto",  # vision_details
        None,  # reasoning_effort
        None,  # http_client_proxies
        None,  # is_reasoning_model
        base_url,  # openai_base_url (historical 12th positional slot)
    )
    assert config.openai_base_url == base_url
    assert config.max_retries == 0


def test_no_retry_by_default_propagates_original_error(mock_openai_client):
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14")  # max_retries defaults to 0
    llm = OpenAILLM(config)
    mock_openai_client.chat.completions.create.side_effect = _timeout_error()

    with patch("time.sleep") as sleep:
        with pytest.raises(openai.APITimeoutError):
            llm.generate_response([{"role": "user", "content": "hi"}])

    assert mock_openai_client.chat.completions.create.call_count == 1
    sleep.assert_not_called()


def test_retries_transient_error_then_succeeds(mock_openai_client):
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", max_retries=2)
    llm = OpenAILLM(config)
    mock_openai_client.chat.completions.create.side_effect = [_timeout_error(), _ok()]

    with patch("time.sleep"):
        response = llm.generate_response([{"role": "user", "content": "hi"}])

    assert response == "ok"
    assert mock_openai_client.chat.completions.create.call_count == 2


def test_raises_mem0_rate_limit_error_after_exhaustion(mock_openai_client):
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", max_retries=1)
    llm = OpenAILLM(config)
    mock_openai_client.chat.completions.create.side_effect = _rate_limit_error(retry_after=0)

    with patch("time.sleep"):
        with pytest.raises(RateLimitError):
            llm.generate_response([{"role": "user", "content": "hi"}])

    assert mock_openai_client.chat.completions.create.call_count == 2  # 1 initial + 1 retry


def test_does_not_retry_authentication_error(mock_openai_client):
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", max_retries=3)
    llm = OpenAILLM(config)
    mock_openai_client.chat.completions.create.side_effect = _auth_error()

    with patch("time.sleep") as sleep:
        with pytest.raises(openai.AuthenticationError):
            llm.generate_response([{"role": "user", "content": "hi"}])

    assert mock_openai_client.chat.completions.create.call_count == 1
    sleep.assert_not_called()


class _HeaderError(Exception):
    """Minimal stand-in for an OpenAI error carrying a response with headers."""

    def __init__(self, headers):
        self.response = type("_Resp", (), {"headers": headers})()


def test_retry_after_ms_header_takes_precedence():
    # retry-after-ms (milliseconds) wins over retry-after (seconds), matching the OpenAI SDK.
    assert _openai_retry_after(_HeaderError({"retry-after-ms": "2000", "retry-after": "9"})) == 2.0


def test_retry_after_numeric_seconds():
    assert _openai_retry_after(_HeaderError({"retry-after": "5"})) == 5.0


def test_retry_after_http_date_is_parsed():
    # A past HTTP-date parses to a negative delay (retry_call then ignores it and falls
    # back to backoff); a far-future date parses to a positive delay.
    past = _openai_retry_after(_HeaderError({"retry-after": "Wed, 21 Oct 2015 07:28:00 GMT"}))
    future = _openai_retry_after(_HeaderError({"retry-after": "Wed, 21 Oct 2099 07:28:00 GMT"}))
    assert past is not None and past < 0
    assert future is not None and future > 0


def test_retry_after_malformed_returns_none():
    assert _openai_retry_after(_HeaderError({"retry-after": "soon"})) is None


def test_retry_after_absent_returns_none():
    assert _openai_retry_after(_HeaderError({})) is None
    assert _openai_retry_after(Exception("no response attribute")) is None


def _internal_server_error():
    resp = httpx.Response(500, request=_req())
    return openai.InternalServerError("server boom", response=resp, body=None)


def test_timeout_exhaustion_raises_network_error_chained(mock_openai_client):
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", max_retries=1)
    llm = OpenAILLM(config)
    mock_openai_client.chat.completions.create.side_effect = _timeout_error()

    with patch("time.sleep"):
        with pytest.raises(NetworkError) as excinfo:
            llm.generate_response([{"role": "user", "content": "hi"}])

    assert isinstance(excinfo.value.__cause__, openai.APITimeoutError)


def test_internal_server_error_exhaustion_raises_llm_error_chained(mock_openai_client):
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", max_retries=1)
    llm = OpenAILLM(config)
    mock_openai_client.chat.completions.create.side_effect = _internal_server_error()

    with patch("time.sleep"):
        with pytest.raises(LLMError) as excinfo:
            llm.generate_response([{"role": "user", "content": "hi"}])

    assert isinstance(excinfo.value.__cause__, openai.InternalServerError)


@pytest.mark.parametrize("bad", ["1", 0.5, -1, True])
def test_config_rejects_invalid_max_retries(bad):
    # max_retries is an integer retry-count knob: reject non-int / negative / bool so a
    # misconfig fails fast at construction instead of crashing later at `max_retries <= 0`
    # (e.g. a dict config {"max_retries": "1"}).
    with pytest.raises(ValueError):
        OpenAIConfig(model="gpt-4.1-nano-2025-04-14", max_retries=bad)


def test_dict_config_invalid_max_retries_raises_valueerror():
    with pytest.raises(ValueError):
        OpenAILLM({"model": "gpt-4.1-nano-2025-04-14", "max_retries": "1"})
