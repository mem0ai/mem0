import unittest

from embedchain import App
from embedchain.config import AppConfig


class TestApp(unittest.TestCase):
    def test_app_init(self):
        """
        Test that app can be instantiated with config.
        """
        config = AppConfig()
        app = App(config=config)

        # Assert that app is not None
        self.assertIsNotNone(app)

        # Assert that app is an instance of App
        self.assertIsInstance(app, App)
