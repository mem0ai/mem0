import os
from unittest.mock import MagicMock, patch

import pytest

from embedchain import App
from embedchain.config import AppConfig, BaseLlmConfig
from embedchain.llm.openai import OpenAILlm


@pytest.fixture
def app():
    os.environ["OPENAI_API_KEY"] = "test_api_key"
    app = App(config=AppConfig(collect_metrics=False))
    return app


@patch("chromadb.api.models.Collection.Collection.add", MagicMock)
def test_query(app):
    with patch.object(app, "_retrieve_from_database") as mock_retrieve:
        mock_retrieve.return_value = ["Test context"]
        with patch.object(app.llm, "get_llm_model_answer") as mock_answer:
            mock_answer.return_value = "Test answer"
            answer = app.query(input_query="Test query")
            assert answer == "Test answer"

    mock_retrieve.assert_called_once()
    _, kwargs = mock_retrieve.call_args
    input_query_arg = kwargs.get("input_query")
    assert input_query_arg == "Test query"
    mock_answer.assert_called_once()


@patch("embedchain.llm.openai.OpenAILlm._get_answer")
def test_query_config_app_passing(mock_get_answer):
    mock_get_answer.return_value = MagicMock()
    mock_get_answer.return_value = "Test answer"

    config = AppConfig(collect_metrics=False)
    chat_config = BaseLlmConfig(system_prompt="Test system prompt")
    llm = OpenAILlm(config=chat_config)
    app = App(config=config, llm=llm)
    answer = app.llm.get_llm_model_answer("Test query")

    assert app.llm.config.system_prompt == "Test system prompt"
    assert answer == "Test answer"


@patch("chromadb.api.models.Collection.Collection.add", MagicMock)
def test_query_with_where_in_params(app):
    with patch.object(app, "_retrieve_from_database") as mock_retrieve:
        mock_retrieve.return_value = ["Test context"]
        with patch.object(app.llm, "get_llm_model_answer") as mock_answer:
            mock_answer.return_value = "Test answer"
            answer = app.query("Test query", where={"attribute": "value"})

    assert answer == "Test answer"
    _, kwargs = mock_retrieve.call_args
    assert kwargs.get("input_query") == "Test query"
    assert kwargs.get("where") == {"attribute": "value"}
    mock_answer.assert_called_once()


@patch("chromadb.api.models.Collection.Collection.add", MagicMock)
def test_query_with_where_in_query_config(app):
    with patch.object(app.llm, "get_llm_model_answer") as mock_answer:
        mock_answer.return_value = "Test answer"
        with patch.object(app.db, "query") as mock_database_query:
            mock_database_query.return_value = ["Test context"]
            llm_config = BaseLlmConfig(where={"attribute": "value"})
            answer = app.query("Test query", llm_config)

    assert answer == "Test answer"
    _, kwargs = mock_database_query.call_args
    assert kwargs.get("input_query") == "Test query"
    where = kwargs.get("where")
    assert "app_id" in where
    assert "attribute" in where
    mock_answer.assert_called_once()
