import os
import unittest

import yaml

from embedchain import App, CustomApp, Llama2App, OpenSourceApp
from embedchain.config import ChromaDbConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.llm.base import BaseLlm
from embedchain.vectordb.base import BaseVectorDB
from embedchain.vectordb.chroma import ChromaDB


class TestApps(unittest.TestCase):
    try:
        del os.environ["OPENAI_KEY"]
    except KeyError:
        pass

    def test_app(self):
        app = App()
        self.assertIsInstance(app.llm, BaseLlm)
        self.assertIsInstance(app.db, BaseVectorDB)
        self.assertIsInstance(app.embedder, BaseEmbedder)

    def test_custom_app(self):
        app = CustomApp()
        self.assertIsInstance(app.llm, BaseLlm)
        self.assertIsInstance(app.db, BaseVectorDB)
        self.assertIsInstance(app.embedder, BaseEmbedder)

    def test_opensource_app(self):
        app = OpenSourceApp()
        self.assertIsInstance(app.llm, BaseLlm)
        self.assertIsInstance(app.db, BaseVectorDB)
        self.assertIsInstance(app.embedder, BaseEmbedder)

    def test_llama2_app(self):
        os.environ["REPLICATE_API_TOKEN"] = "-"
        app = Llama2App()
        self.assertIsInstance(app.llm, BaseLlm)
        self.assertIsInstance(app.db, BaseVectorDB)
        self.assertIsInstance(app.embedder, BaseEmbedder)


class TestConfigForAppComponents(unittest.TestCase):
    collection_name = "my-test-collection"

    def test_constructor_config(self):
        """
        Test that app can be configured through the app constructor.
        """
        app = App(db_config=ChromaDbConfig(collection_name=self.collection_name))
        self.assertEqual(app.db.config.collection_name, self.collection_name)

    def test_component_config(self):
        """
        Test that app can also be configured by passing a configured component to the app
        """
        database = ChromaDB(config=ChromaDbConfig(collection_name=self.collection_name))
        app = App(db=database)
        self.assertEqual(app.db.config.collection_name, self.collection_name)


class TestAppFromConfig:
    def load_config_data(self, yaml_path):
        with open(yaml_path, "r") as file:
            return yaml.safe_load(file)

    def test_from_chroma_config(self):
        yaml_path = "embedchain/yaml/chroma.yaml"
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

    def test_from_opensource_config(self):
        yaml_path = "embedchain/yaml/opensource.yaml"
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

    def test_from_opensearch_config(self):
        yaml_path = "embedchain/yaml/opensearch.yaml"
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
        assert app.llm.config.temperature == llm_config["temperature"]
        assert app.llm.config.max_tokens == llm_config["max_tokens"]
        assert app.llm.config.top_p == llm_config["top_p"]
        assert app.llm.config.stream == llm_config["stream"]

        # Validate the VectorDB config values
        db_config = config_data["vectordb"]["config"]
        assert app.db.config.collection_name == db_config["collection_name"]
        assert app.db.config.opensearch_url == db_config["opensearch_url"]
        assert app.db.config.http_auth == db_config["http_auth"]
        assert app.db.config.vector_dimension == db_config["vector_dimension"]

        # Validate the Embedder config values
        embedder_config = config_data["embedder"]["config"]
        assert app.embedder.config.model == embedder_config["model"]
        assert app.embedder.config.deployment_name == embedder_config["deployment_name"]
