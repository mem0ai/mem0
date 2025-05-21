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


# ASIF: Adding new tests for custom LLM integration
import unittest
from unittest.mock import patch
import tempfile
import shutil
# Assuming App is imported from embedchain.app based on previous file reading
# from embedchain.app import App # Already imported at the top as `from embedchain import App`
# BaseLlmConfig from embedchain.config.llm.base will be used by LlmFactory
# For Embedder, let's use a minimal config for OpenAIEmbedder or a dummy one.

class TestAppCustomLlmIntegration(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for ChromaDB
        self.temp_dir = tempfile.mkdtemp()
        # Mock OPENAI_API_KEY for the default embedder if not overridden
        # Or ensure the chosen embedder doesn't require real keys for init.
        # The tests will use a dummy "openai" embedder for simplicity.
        os.environ["OPENAI_API_KEY"] = "fake_openai_key_for_embedder"


    def tearDown(self):
        # Remove the temporary directory
        shutil.rmtree(self.temp_dir)
        if "OPENAI_API_KEY" in os.environ and os.environ["OPENAI_API_KEY"] == "fake_openai_key_for_embedder":
            del os.environ["OPENAI_API_KEY"]


    @patch('mem0.llms.silicon_life.SiliconLifeLLM.generate_response')
    def test_siliconlife_llm_integration(self, mock_generate_response):
        mock_generate_response.return_value = "Mocked SiliconLife response"

        app_config_dict = {
            "app": {"config": {"id": "test_sl_app"}}, # Minimal app config
            "llm": {
                "provider": "siliconlife",
                "config": {
                    "model": "test-silicon-model",
                    "api_key": "fake_sl_api_key",
                    # The SiliconLifeLLM __init__ uses getattr(self.config, 'silicon_life_base_url', default_url)
                    # So we should provide it here.
                    "silicon_life_base_url": "https://mock.api.siliconlife.ai/v1/custom" 
                }
            },
            "vectordb": {
                "provider": "chroma", 
                "config": {
                    "collection_name": "test_sl_collection", 
                    "dir": self.temp_dir, # Use temp dir
                    "allow_reset": True,
                }
            },
            "embedder": { # Dummy embedder config
                "provider": "openai", 
                "config": {
                    "model": "text-embedding-ada-002", # A common default
                    "api_key": "fake_openai_key_for_embedder" 
                }
            }
        }

        # Use App.from_config to instantiate with the dictionary
        app = App.from_config(config=app_config_dict)
        
        # Add some data to query against, otherwise query might not call LLM
        app.add("Test data for SiliconLife query")

        # Perform a query
        response = app.query("Some query to SiliconLife")

        # Assertions
        mock_generate_response.assert_called_once()
        # The actual messages passed to generate_response will be complex due to prompt formatting
        # So, we mainly check if it was called and if the final response matches.
        self.assertEqual(response, "Mocked SiliconLife response")

    @patch('mem0.llms.deepseek.DeepseekLLM.generate_response')
    def test_deepseek_llm_integration(self, mock_generate_response):
        mock_generate_response.return_value = "Mocked Deepseek response"

        app_config_dict = {
            "app": {"config": {"id": "test_ds_app"}},
            "llm": {
                "provider": "deepseek",
                "config": {
                    "model": "test-deepseek-model",
                    "api_key": "fake_ds_api_key",
                    # DeepseekLLM __init__ uses self.config.deepseek_base_url
                    "deepseek_base_url": "https://mock.api.deepseek.com/v1/custom"
                }
            },
            "vectordb": {
                "provider": "chroma", 
                "config": {
                    "collection_name": "test_ds_collection", 
                    "dir": self.temp_dir, # Use temp dir
                    "allow_reset": True,
                }
            },
            "embedder": {
                "provider": "openai", 
                "config": {
                    "model": "text-embedding-ada-002",
                    "api_key": "fake_openai_key_for_embedder"
                }
            }
        }

        app = App.from_config(config=app_config_dict)
        
        app.add("Test data for Deepseek query")

        response = app.query("Some query to Deepseek")

        mock_generate_response.assert_called_once()
        self.assertEqual(response, "Mocked Deepseek response")
