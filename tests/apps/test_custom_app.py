import unittest

from embedchain import CustomApp
from embedchain.config import CustomAppConfig
from embedchain.models import EmbeddingFunctions, Providers


class TestCustomApp(unittest.TestCase):
    def test_app_init_openai_openai(self):
        """
        Test that app can be instantiated with config.
        """
        config = CustomAppConfig(provider=Providers.OPENAI, embedding_fn=EmbeddingFunctions.OPENAI)
        print(vars(config))
        app = CustomApp(config=config)

        # Assert that app is not None
        self.assertIsNotNone(app)

        # Assert that app is an instance of App
        self.assertIsInstance(app, CustomApp)

    def test_app_init_gpt4all_gpt4all(self):
        """
        Test that app can be instantiated with config.
        """
        config = CustomAppConfig(provider=Providers.GPT4ALL, embedding_fn=EmbeddingFunctions.GPT4ALL)
        print(vars(config))
        app = CustomApp(config=config)

        # Assert that app is not None
        self.assertIsNotNone(app)

        # Assert that app is an instance of App
        self.assertIsInstance(app, CustomApp)

    # TODO: Other apps require extra dependencies. We need to decide how to deal with those.
