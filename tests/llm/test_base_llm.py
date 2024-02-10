from string import Template

import pytest

from embedchain.llm.base import BaseLlm, BaseLlmConfig


@pytest.fixture
def base_llm():
    config = BaseLlmConfig()
    return BaseLlm(config=config)


def test_is_get_llm_model_answer_not_implemented(base_llm):
    with pytest.raises(NotImplementedError):
        base_llm.get_llm_model_answer()


def test_is_stream_bool():
    with pytest.raises(ValueError):
        config = BaseLlmConfig(stream="test value")
        BaseLlm(config=config)


def test_template_string_gets_converted_to_Template_instance():
    config = BaseLlmConfig(template="test value $query $context")
    llm = BaseLlm(config=config)
    assert isinstance(llm.config.prompt, Template)


def test_is_get_llm_model_answer_implemented():
    class TestLlm(BaseLlm):
        def get_llm_model_answer(self):
            return "Implemented"

    config = BaseLlmConfig()
    llm = TestLlm(config=config)
    assert llm.get_llm_model_answer() == "Implemented"


def test_stream_response(base_llm):
    answer = ["Chunk1", "Chunk2", "Chunk3"]
    result = list(base_llm._stream_response(answer))
    assert result == answer


def test_append_search_and_context(base_llm):
    context = "Context"
    web_search_result = "Web Search Result"
    result = base_llm._append_search_and_context(context, web_search_result)
    expected_result = "Context\nWeb Search Result: Web Search Result"
    assert result == expected_result


def test_access_search_and_get_results(base_llm, mocker):
    base_llm.access_search_and_get_results = mocker.patch.object(
        base_llm, "access_search_and_get_results", return_value="Search Results"
    )
    input_query = "Test query"
    result = base_llm.access_search_and_get_results(input_query)
    assert result == "Search Results"
