import os
import unittest

from embedchain import App, CustomApp, Llama2App, OpenSourceApp
from embedchain.embedder.base import BaseEmbedder
from embedchain.llm.base import BaseLlm
from embedchain.vectordb.base import BaseVectorDB


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
