import importlib
import os

import pytest

from embedchain.config import BaseLlmConfig
from embedchain.llm.huggingface import HuggingFaceLlm


@pytest.fixture
def huggingface_llm_config():
    os.environ["HUGGINGFACE_ACCESS_TOKEN"] = "test_access_token"
    config = BaseLlmConfig(model="google/flan-t5-xxl", max_tokens=50, temperature=0.7, top_p=0.8)
    yield config
    os.environ.pop("HUGGINGFACE_ACCESS_TOKEN")


@pytest.fixture
def huggingface_endpoint_config():
    os.environ["HUGGINGFACE_ACCESS_TOKEN"] = "test_access_token"
    config = BaseLlmConfig(endpoint="https://api-inference.huggingface.co/models/gpt2", model_kwargs={"device": "cpu"})
    yield config
    os.environ.pop("HUGGINGFACE_ACCESS_TOKEN")


def test_init_raises_value_error_without_api_key(mocker):
    mocker.patch.dict(os.environ, clear=True)
    with pytest.raises(ValueError):
        HuggingFaceLlm()


def test_get_llm_model_answer_raises_value_error_for_system_prompt(huggingface_llm_config):
    llm = HuggingFaceLlm(huggingface_llm_config)
    llm.config.system_prompt = "system_prompt"
    with pytest.raises(ValueError):
        llm.get_llm_model_answer("prompt")


def test_top_p_value_within_range():
    config = BaseLlmConfig(top_p=1.0)
    with pytest.raises(ValueError):
        HuggingFaceLlm._get_answer("test_prompt", config)


def test_dependency_is_imported():
    importlib_installed = True
    try:
        importlib.import_module("huggingface_hub")
    except ImportError:
        importlib_installed = False
    assert importlib_installed


def test_get_llm_model_answer(huggingface_llm_config, mocker):
    mocker.patch("embedchain.llm.huggingface.HuggingFaceLlm._get_answer", return_value="Test answer")

    llm = HuggingFaceLlm(huggingface_llm_config)
    answer = llm.get_llm_model_answer("Test query")

    assert answer == "Test answer"


def test_hugging_face_mock(huggingface_llm_config, mocker):
    mock_llm_instance = mocker.Mock(return_value="Test answer")
    mock_hf_hub = mocker.patch("embedchain.llm.huggingface.HuggingFaceHub")
    mock_hf_hub.return_value.invoke = mock_llm_instance

    llm = HuggingFaceLlm(huggingface_llm_config)
    answer = llm.get_llm_model_answer("Test query")
    assert answer == "Test answer"
    mock_llm_instance.assert_called_once_with("Test query")


def test_custom_endpoint(huggingface_endpoint_config, mocker):
    mock_llm_instance = mocker.Mock(return_value="Test answer")
    mock_hf_endpoint = mocker.patch("embedchain.llm.huggingface.HuggingFaceEndpoint")
    mock_hf_endpoint.return_value.invoke = mock_llm_instance

    llm = HuggingFaceLlm(huggingface_endpoint_config)
    answer = llm.get_llm_model_answer("Test query")

    assert answer == "Test answer"
    mock_llm_instance.assert_called_once_with("Test query")
