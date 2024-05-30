import os

import pytest
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

from embedchain.config import BaseLlmConfig
from embedchain.llm.zhipuai import ZhipuAILlm
from embedchain.core.db.database import get_session, init_db, setup_engine

# 函数级，前置函数
def setup_function():
    setup_engine(database_uri=os.environ.get("EMBEDCHAIN_DB_URI"))
    # init_db()

@pytest.fixture
def config():

    os.environ["ZHIPU_API_KEY"] = "test_api_key"
    config = BaseLlmConfig(
        temperature=0.7, max_tokens=50, top_p=0.8, stream=False, system_prompt="System prompt", model="glm-4"
    )
    yield config
    os.environ.pop("ZHIPU_API_KEY")


def test_get_llm_model_answer(config, mocker):
    mocked_get_answer = mocker.patch("embedchain.llm.zhipuai.ZhipuAILlm._get_answer", return_value="Test answer")

    llm = ZhipuAILlm(config)
    answer = llm.get_llm_model_answer("Test query")

    assert answer == "Test answer"
    mocked_get_answer.assert_called_once_with("Test query", config)


def test_get_llm_model_answer_with_system_prompt(config, mocker):
    config.system_prompt = "Custom system prompt"
    mocked_get_answer = mocker.patch("embedchain.llm.zhipuai.ZhipuAILlm._get_answer", return_value="Test answer")

    llm = ZhipuAILlm(config)
    answer = llm.get_llm_model_answer("Test query")

    assert answer == "Test answer"
    mocked_get_answer.assert_called_once_with("Test query", config)


def test_get_llm_model_answer_empty_prompt(config, mocker):
    mocked_get_answer = mocker.patch("embedchain.llm.zhipuai.ZhipuAILlm._get_answer", return_value="Test answer")

    llm = ZhipuAILlm(config)
    answer = llm.get_llm_model_answer("")

    assert answer == "Test answer"
    mocked_get_answer.assert_called_once_with("", config)





def test_get_llm_model_answer_without_system_prompt(config, mocker):
    config.system_prompt = None
    mocked_zhipuai_chat = mocker.patch("embedchain.llm.zhipuai.ZhipuAI")

    llm = ZhipuAILlm(config)
    llm.get_llm_model_answer("Test query")

    mocked_zhipuai_chat.assert_called_once_with(
        api_key=os.environ["ZHIPU_API_KEY"],
    )


