import os

import pytest
import yaml

from embedchain import App
from embedchain.config import ChromaDbConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.llm.base import BaseLlm
from embedchain.vectordb.base import BaseVectorDB
from embedchain.vectordb.chroma import ChromaDB


@pytest.fixture
def app():
    os.environ["OPENAI_API_KEY"] = "test-api-key"
    os.environ["OPENAI_API_BASE"] = "test-api-base"
    return App()


def test_app(app):
    assert isinstance(app.llm, BaseLlm)
    assert isinstance(app.db, BaseVectorDB)
    assert isinstance(app.embedding_model, BaseEmbedder)


class TestConfigForAppComponents:
    def test_constructor_config(self):
        collection_name = "my-test-collection"
        db = ChromaDB(config=ChromaDbConfig(collection_name=collection_name))
        app = App(db=db)
        assert app.db.config.collection_name == collection_name

    def test_component_config(self):
        collection_name = "my-test-collection"
        database = ChromaDB(config=ChromaDbConfig(collection_name=collection_name))
        app = App(db=database)
        assert app.db.config.collection_name == collection_name


class TestAppFromConfig:
    def load_config_data(self, yaml_path):
        with open(yaml_path, "r") as file:
            return yaml.safe_load(file)

    def test_from_chroma_config(self, mocker):
        mocker.patch("embedchain.vectordb.chroma.chromadb.Client")

        yaml_path = "configs/chroma.yaml"
        config_data = self.load_config_data(yaml_path)

        app = App.from_config(config_path=yaml_path)

        # Check if the App instance and its components were created correctly
        assert isinstance(app, App)

        # Validate the AppConfig values
        assert app.config.id == config_data["app"]["config"]["id"]
        # Even though not present in the config, the default value is used
        assert app.config.collect_metrics is True

        # Validate the LLM config values
        llm_config = config_data["llm"]["config"]
        assert app.llm.config.temperature == llm_config["temperature"]
        assert app.llm.config.max_tokens == llm_config["max_tokens"]
        assert app.llm.config.top_p == llm_config["top_p"]
        assert app.llm.config.stream == llm_config["stream"]

        # Validate the VectorDB config values
        db_config = config_data["vectordb"]["config"]
        assert app.db.config.collection_name == db_config["collection_name"]
        assert app.db.config.dir == db_config["dir"]
        assert app.db.config.allow_reset == db_config["allow_reset"]

        # Validate the Embedder config values
        embedder_config = config_data["embedder"]["config"]
        assert app.embedding_model.config.model == embedder_config["model"]
        assert app.embedding_model.config.deployment_name == embedder_config.get("deployment_name")

    def test_from_opensource_config(self, mocker):
        mocker.patch("embedchain.vectordb.chroma.chromadb.Client")

        yaml_path = "configs/opensource.yaml"
        config_data = self.load_config_data(yaml_path)

        app = App.from_config(yaml_path)

        # Check if the App instance and its components were created correctly
        assert isinstance(app, App)

        # Validate the AppConfig values
        assert app.config.id == config_data["app"]["config"]["id"]
        assert app.config.collect_metrics == config_data["app"]["config"]["collect_metrics"]

        # Validate the LLM config values
        llm_config = config_data["llm"]["config"]
        assert app.llm.config.model == llm_config["model"]
        assert app.llm.config.temperature == llm_config["temperature"]
        assert app.llm.config.max_tokens == llm_config["max_tokens"]
        assert app.llm.config.top_p == llm_config["top_p"]
        assert app.llm.config.stream == llm_config["stream"]

        # Validate the VectorDB config values
        db_config = config_data["vectordb"]["config"]
        assert app.db.config.collection_name == db_config["collection_name"]
        assert app.db.config.dir == db_config["dir"]
        assert app.db.config.allow_reset == db_config["allow_reset"]

        # Validate the Embedder config values
        embedder_config = config_data["embedder"]["config"]
        assert app.embedding_model.config.deployment_name == embedder_config["deployment_name"]
