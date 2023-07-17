import os
import unittest
from unittest.mock import patch

from embedchain import App
from embedchain.config import AppConfig


class TestChromaDbHostsLoglevel(unittest.TestCase):
    os.environ["OPENAI_API_KEY"] = "test_key"

    @patch("chromadb.api.models.Collection.Collection.add")
    @patch("chromadb.api.models.Collection.Collection.get")
    @patch("embedchain.embedchain.EmbedChain.retrieve_from_database")
    @patch("embedchain.embedchain.EmbedChain.get_answer_from_llm")
    @patch("embedchain.embedchain.EmbedChain.get_llm_model_answer")
    def test_whole_app(
        self,
        _mock_get,
        _mock_add,
        _mock_ec_retrieve_from_database,
        _mock_get_answer_from_llm,
        mock_ec_get_llm_model_answer,
    ):
        """
        Test if the `App` instance is initialized without a config that does not contain default hosts and ports.
        """
        config = AppConfig(log_level="DEBUG")

        app = App(config)

        knowledge = "lorem ipsum dolor sit amet, consectetur adipiscing"

        app.add_local("text", knowledge)

        app.query("What text did I give you?")
        app.chat("What text did I give you?")

        self.assertEqual(mock_ec_get_llm_model_answer.call_args[1]["documents"], [knowledge])
