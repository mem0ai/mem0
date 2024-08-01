import pytest
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

from embedchain.config import BaseLlmConfig
from embedchain.llm.aws_bedrock import AWSBedrockLlm


@pytest.fixture
def config(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test_access_key_id")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test_secret_access_key")
    config = BaseLlmConfig(
        model="amazon.titan-text-express-v1",
        model_kwargs={
            "temperature": 0.5,
            "topP": 1,
            "maxTokenCount": 1000,
        },
    )
    yield config
    monkeypatch.delenv("AWS_ACCESS_KEY_ID")
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY")


def test_get_llm_model_answer(config, mocker):
    mocked_get_answer = mocker.patch("embedchain.llm.aws_bedrock.AWSBedrockLlm._get_answer", return_value="Test answer")

    llm = AWSBedrockLlm(config)
    answer = llm.get_llm_model_answer("Test query")

    assert answer == "Test answer"
    mocked_get_answer.assert_called_once_with("Test query", config)


def test_get_llm_model_answer_empty_prompt(config, mocker):
    mocked_get_answer = mocker.patch("embedchain.llm.aws_bedrock.AWSBedrockLlm._get_answer", return_value="Test answer")

    llm = AWSBedrockLlm(config)
    answer = llm.get_llm_model_answer("")

    assert answer == "Test answer"
    mocked_get_answer.assert_called_once_with("", config)


def test_get_llm_model_answer_with_streaming(config, mocker):
    config.stream = True
    mocked_bedrock_chat = mocker.patch("embedchain.llm.aws_bedrock.BedrockLLM")

    llm = AWSBedrockLlm(config)
    llm.get_llm_model_answer("Test query")

    mocked_bedrock_chat.assert_called_once()
    callbacks = [callback[1]["callbacks"] for callback in mocked_bedrock_chat.call_args_list]
    assert any(isinstance(callback[0], StreamingStdOutCallbackHandler) for callback in callbacks)
