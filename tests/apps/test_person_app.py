import pytest

from embedchain.apps.app import App
from embedchain.apps.person_app import PersonApp, PersonOpenSourceApp
from embedchain.config import AppConfig, BaseLlmConfig
from embedchain.config.llm.base import DEFAULT_PROMPT


@pytest.fixture
def person_app():
    config = AppConfig()
    return PersonApp("John Doe", config)


@pytest.fixture
def opensource_person_app():
    config = AppConfig()
    return PersonOpenSourceApp("John Doe", config)


def test_person_app_initialization(person_app):
    assert person_app.person == "John Doe"
    assert f"You are {person_app.person}" in person_app.person_prompt
    assert isinstance(person_app.config, AppConfig)


def test_person_app_add_person_template_to_config_with_invalid_template():
    app = PersonApp("John Doe")
    default_prompt = "Input Prompt"
    with pytest.raises(ValueError):
        # as prompt doesn't contain $context and $query
        app.add_person_template_to_config(default_prompt)


def test_person_app_add_person_template_to_config_with_valid_template():
    app = PersonApp("John Doe")
    config = app.add_person_template_to_config(DEFAULT_PROMPT)
    assert (
        config.template.template
        == f"You are John Doe. Whatever you say, you will always say in John Doe style. {DEFAULT_PROMPT}"
    )


def test_person_app_query(mocker, person_app):
    input_query = "Hello, how are you?"
    config = BaseLlmConfig()

    mocker.patch.object(App, "query", return_value="Mocked response")

    result = person_app.query(input_query, config)
    assert result == "Mocked response"


def test_person_app_chat(mocker, person_app):
    input_query = "Hello, how are you?"
    config = BaseLlmConfig()

    mocker.patch.object(App, "chat", return_value="Mocked chat response")

    result = person_app.chat(input_query, config)
    assert result == "Mocked chat response"


def test_opensource_person_app_query(mocker, opensource_person_app):
    input_query = "Hello, how are you?"
    config = BaseLlmConfig()

    mocker.patch.object(App, "query", return_value="Mocked response")

    result = opensource_person_app.query(input_query, config)
    assert result == "Mocked response"


def test_opensource_person_app_chat(mocker, opensource_person_app):
    input_query = "Hello, how are you?"
    config = BaseLlmConfig()

    mocker.patch.object(App, "chat", return_value="Mocked chat response")

    result = opensource_person_app.chat(input_query, config)
    assert result == "Mocked chat response"
