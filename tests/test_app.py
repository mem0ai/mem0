import os

import pytest

from embedchain.app import App


@pytest.fixture
def app_instance():
    os.environ["OPENAI_API_KEY"] = "test_api_key"
    return App()


def test_app_initialization(app_instance):
    assert isinstance(app_instance, App)
    assert app_instance.id is None
    assert app_instance.name is None
    assert app_instance.config is not None
    assert app_instance.db is None
    assert app_instance.embedding_model is None
    assert app_instance.llm is None
    assert app_instance.config_data is None
    assert app_instance.auto_deploy is False
    assert app_instance.chunker is None
