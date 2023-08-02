import unittest
from embedchain import OpenSourceApp
from embedchain.config import OpenSourceAppConfig

class TestChromaDbHosts(unittest.TestCase):
    def test_app_init(self):
        """
        Test that app can be instantiated with config.
        """
        config = OpenSourceAppConfig()
        app = OpenSourceApp(config=config)

        # Assert that app is not None
        self.assertIsNotNone(app)

        # Assert that app is an instance of App
        self.assertIsInstance(app, OpenSourceApp)
