import os
import unittest

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
