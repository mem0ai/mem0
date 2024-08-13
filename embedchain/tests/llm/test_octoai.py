import os
import pytest
from embedchain.config import BaseLlmConfig

from embedchain.llm.octoai import OctoAILlm

@pytest.fixture
def octoai_env():
    os.environ["OCTOAI_API_TOKEN"] = "test_api_token"
    yield
    del os.environ["OCTOAI_API_TOKEN"]

@pytest.fixture
def octoai_llm_config():
    config = BaseLlmConfig(
        temperature=0.7,
        model="llama-2-13b-chat-fp16",
        max_tokens=50,
        top_p=0.9,
    )
    return config


def test_get_answer(octoai_llm_config, octoai_env, mocker):
    mocked_get_answer = mocker.patch("embedchain.llm.octoai.OctoAILlm._get_answer", return_value="Test answer")

    octoai_llm = OctoAILlm(octoai_llm_config)
    answer = octoai_llm.get_llm_model_answer("Test query")

    assert answer == "Test answer"
    mocked_get_answer.assert_called_once()

def test_octo_env_variable(octoai_llm_config):

    with pytest.raises(AssertionError):
        _ = OctoAILlm(octoai_llm_config)
