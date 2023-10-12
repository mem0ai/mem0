import os
import unittest

from embedchain import App, CustomApp, Llama2App, OpenSourceApp
from embedchain.config import ChromaDbConfig, AppConfig, AddConfig, BaseLlmConfig, BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.llm.base import BaseLlm
from embedchain.vectordb.base import BaseVectorDB, BaseVectorDbConfig
from embedchain.vectordb.chroma import ChromaDB


class TestApps(unittest.TestCase):
    os.environ["OPENAI_API_KEY"] = "test_api_key"

    def test_app(self):
        app = App()
        self.assertIsInstance(app.llm, BaseLlm)
        self.assertIsInstance(app.db, BaseVectorDB)
        self.assertIsInstance(app.embedder, BaseEmbedder)

        wrong_llm = "wrong_llm"
        with self.assertRaises(TypeError):
            App(llm=wrong_llm)

        wrong_db = "wrong_db"
        with self.assertRaises(TypeError):
            App(db=wrong_db)

        wrong_embedder = "wrong_embedder"
        with self.assertRaises(TypeError):
            App(embedder=wrong_embedder)

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

    def test_different_configs_are_proper_instances(self):
        config = AppConfig()
        wrong_app_config = AddConfig()

        with self.assertRaises(TypeError):
            App(config=wrong_app_config)

        self.assertIsInstance(config, AppConfig)

        llm_config = BaseLlmConfig()
        wrong_llm_config = "wrong_llm_config"

        with self.assertRaises(TypeError):
            App(llm_config=wrong_llm_config)

        self.assertIsInstance(llm_config, BaseLlmConfig)

        db_config = BaseVectorDbConfig()
        wrong_db_config = "wrong_db_config"

        with self.assertRaises(TypeError):
            App(db_config=wrong_db_config)

        self.assertIsInstance(db_config, BaseVectorDbConfig)

        embedder_config = BaseEmbedderConfig()
        wrong_embedder_config = "wrong_embedder_config"

        with self.assertRaises(TypeError):
            App(embedder_config=wrong_embedder_config)

        self.assertIsInstance(embedder_config, BaseEmbedderConfig)
