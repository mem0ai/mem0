import os

import pytest
import yaml

from embedchain import App
from embedchain.config import (AddConfig, AppConfig, BaseEmbedderConfig,
                               BaseLlmConfig, ChromaDbConfig)
from embedchain.embedder.base import BaseEmbedder
from embedchain.llm.base import BaseLlm
from embedchain.vectordb.base import BaseVectorDB, BaseVectorDbConfig
from embedchain.vectordb.chroma import ChromaDB


@pytest.fixture
def app():
    os.environ["OPENAI_API_KEY"] = "test_api_key"
    return App()


def test_app(app):
    assert isinstance(app.llm, BaseLlm)
    assert isinstance(app.db, BaseVectorDB)
    assert isinstance(app.embedder, BaseEmbedder)


class TestConfigForAppComponents:
    def test_constructor_config(self):
        collection_name = "my-test-collection"
        app = App(db_config=ChromaDbConfig(collection_name=collection_name))
        assert app.db.config.collection_name == collection_name

    def test_component_config(self):
        collection_name = "my-test-collection"
        database = ChromaDB(config=ChromaDbConfig(collection_name=collection_name))
        app = App(db=database)
        assert app.db.config.collection_name == collection_name

    def test_different_configs_are_proper_instances(self):
        app_config = AppConfig()
        wrong_config = AddConfig()
        with pytest.raises(TypeError):
            App(config=wrong_config)

        assert isinstance(app_config, AppConfig)

        llm_config = BaseLlmConfig()
        wrong_llm_config = "wrong_llm_config"

        with pytest.raises(TypeError):
            App(llm_config=wrong_llm_config)

        assert isinstance(llm_config, BaseLlmConfig)

        db_config = BaseVectorDbConfig()
        wrong_db_config = "wrong_db_config"

        with pytest.raises(TypeError):
            App(db_config=wrong_db_config)

        assert isinstance(db_config, BaseVectorDbConfig)

        embedder_config = BaseEmbedderConfig()
        wrong_embedder_config = "wrong_embedder_config"
        with pytest.raises(TypeError):
            App(embedder_config=wrong_embedder_config)

        assert isinstance(embedder_config, BaseEmbedderConfig)

    def test_components_raises_type_error_if_not_proper_instances(self):
        wrong_llm = "wrong_llm"
        with pytest.raises(TypeError):
            App(llm=wrong_llm)

        wrong_db = "wrong_db"
        with pytest.raises(TypeError):
            App(db=wrong_db)

        wrong_embedder = "wrong_embedder"
        with pytest.raises(TypeError):
            App(embedder=wrong_embedder)


class TestAppFromConfig:
    def load_config_data(self, yaml_path):
        with open(yaml_path, "r") as file:
            return yaml.safe_load(file)

    def test_from_chroma_config(self, mocker):
        mocker.patch("embedchain.vectordb.chroma.chromadb.Client")

        yaml_path = "configs/chroma.yaml"
        config_data = self.load_config_data(yaml_path)

        app = App.from_config(yaml_path)

        # Check if the App instance and its components were created correctly
        assert isinstance(app, App)

        # Validate the AppConfig values
        assert app.config.id == config_data["app"]["config"]["id"]
        assert app.config.collection_name == config_data["app"]["config"]["collection_name"]
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
        assert app.embedder.config.model == embedder_config["model"]
        assert app.embedder.config.deployment_name == embedder_config["deployment_name"]

    def test_from_opensource_config(self, mocker):
        mocker.patch("embedchain.vectordb.chroma.chromadb.Client")

        yaml_path = "configs/opensource.yaml"
        config_data = self.load_config_data(yaml_path)

        app = App.from_config(yaml_path)

        # Check if the App instance and its components were created correctly
        assert isinstance(app, App)

        # Validate the AppConfig values
        assert app.config.id == config_data["app"]["config"]["id"]
        assert app.config.collection_name == config_data["app"]["config"]["collection_name"]
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
        assert app.embedder.config.deployment_name == embedder_config["deployment_name"]
