from types import SimpleNamespace

import pytest

from mem0.configs.base import MemoryConfig
from mem0.configs.llms.aihubmix import AIHubMixConfig
from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.aihubmix import AIHubMixLLM
from mem0.utils.factory import LlmFactory


@pytest.fixture(autouse=True)
def clean_aihubmix_env(monkeypatch):
    monkeypatch.delenv("AIHUBMIX_API_KEY", raising=False)
    monkeypatch.delenv("AIHUBMIX_BASE_URL", raising=False)


@pytest.fixture
def client(mocker):
    return mocker.patch("mem0.llms.aihubmix.OpenAI").return_value


def test_factory_and_memory_config(client, monkeypatch):
    monkeypatch.setenv("AIHUBMIX_API_KEY", "env-key")
    config = MemoryConfig(llm={"provider": "aihubmix", "config": {}})
    llm = LlmFactory.create(config.llm.provider, config.llm.config)
    assert isinstance(llm, AIHubMixLLM)
    assert llm.config.model == "gpt-6.1-terra"

    dedicated = AIHubMixConfig(aihubmix_base_url="https://custom.example/v1")
    built = LlmFactory.create("aihubmix", dedicated).config
    assert isinstance(built, AIHubMixConfig)
    assert built.model == dedicated.model
    assert built.aihubmix_base_url == dedicated.aihubmix_base_url
    from mem0.llms.aihubmix import OpenAI

    OpenAI.assert_called_with(api_key="env-key", base_url="https://custom.example/v1")
    overridden = LlmFactory.create("aihubmix", dedicated, model="custom-model")
    assert overridden.config.model == "custom-model"
    assert overridden.config.aihubmix_base_url == "https://custom.example/v1"
    assert dedicated.model == "gpt-6.1-terra"
    OpenAI.assert_called_with(api_key="env-key", base_url="https://custom.example/v1")
    base = BaseLlmConfig(model="o3", reasoning_effort="low", is_reasoning_model=True)
    converted = LlmFactory.create("aihubmix", base).config
    assert isinstance(converted, AIHubMixConfig)
    assert (converted.model, converted.reasoning_effort, converted.is_reasoning_model) == ("o3", "low", True)


def test_config_precedence(client, monkeypatch):
    monkeypatch.setenv("AIHUBMIX_API_KEY", "env-key")
    monkeypatch.setenv("AIHUBMIX_BASE_URL", "https://env.example/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "wrong-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "wrong-router-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://wrong.example/v1")
    AIHubMixLLM()
    from mem0.llms.aihubmix import OpenAI

    OpenAI.assert_called_with(api_key="env-key", base_url="https://env.example/v1")
    AIHubMixLLM({"api_key": "explicit", "aihubmix_base_url": "https://explicit.example/v1"})
    OpenAI.assert_called_with(api_key="explicit", base_url="https://explicit.example/v1")
    monkeypatch.delenv("AIHUBMIX_BASE_URL")
    AIHubMixLLM()
    OpenAI.assert_called_with(api_key="env-key", base_url="https://aihubmix.com/v1")


def test_missing_key_does_not_fall_back(client, monkeypatch):
    monkeypatch.delenv("AIHUBMIX_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "wrong-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "wrong-router-key")
    with pytest.raises(ValueError, match="AIHUBMIX_API_KEY"):
        AIHubMixLLM()
    from mem0.llms.aihubmix import OpenAI

    OpenAI.assert_not_called()


def test_json_tools_and_no_openrouter_params(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "wrong-router-key")
    llm = AIHubMixLLM({"api_key": "key", "model": "gpt-6.1-terra"})
    messages = [{"role": "user", "content": "Remember this"}]
    tools = [{"type": "function", "function": {"name": "save"}}]
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=None,
                    tool_calls=[SimpleNamespace(function=SimpleNamespace(name="save", arguments='{"text": "hello"}'))],
                )
            )
        ]
    )
    result = llm.generate_response(
        messages, response_format={"type": "json_object"}, tools=tools, tool_choice="required"
    )
    assert result == {"content": None, "tool_calls": [{"name": "save", "arguments": {"text": "hello"}}]}
    params = client.chat.completions.create.call_args.kwargs
    assert params == {
        "model": "gpt-6.1-terra",
        "messages": messages,
        "temperature": 0.1,
        "top_p": 0.1,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"},
        "tools": tools,
        "tool_choice": "required",
    }

    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok":true}', tool_calls=None))]
    )
    assert llm.generate_response(messages, response_format={"type": "json_object"}) == '{"ok":true}'
    assert "tools" not in client.chat.completions.create.call_args.kwargs


def test_reasoning_param_filter(client):
    llm = AIHubMixLLM({"api_key": "key", "model": "o3", "reasoning_effort": "low"})
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
    )
    assert llm.generate_response([{"role": "user", "content": "hi"}]) == "ok"
    params = client.chat.completions.create.call_args.kwargs
    assert params["reasoning_effort"] == "low"
    assert "temperature" not in params
    assert "max_tokens" not in params
