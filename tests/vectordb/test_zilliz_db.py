# ruff: noqa: E501

import os
from dotenv import load_dotenv

import unittest
from unittest import mock
from unittest.mock import patch

from embedchain import App
from embedchain.config import ZillizDBConfig
from embedchain.vectordb.zilliz import ZillizVectorDB

load_dotenv()


# to run tests, provide the URI and TOKEN in .env file
class TestZillizVectorDBClient(unittest.TestCase):
    @mock.patch.dict(os.environ, {"ZILLIZ_CLOUD_URI": "mocked_uri", "ZILLIZ_CLOUD_TOKEN": "mocked_token"})
    def test_init_with_uri_and_token(self):
        """
        Test if the `ZillizVectorDB` instance is initialized with the correct uri and token values.
        """
        # Create a ZillizDBConfig instance with mocked values
        expected_uri = "mocked_uri"
        expected_token = "mocked_token"
        db_config = ZillizDBConfig()

        # Assert that the values in the ZillizVectorDB instance match the mocked values
        self.assertEqual(db_config.uri, expected_uri)
        self.assertEqual(db_config.token, expected_token)

    @mock.patch.dict(os.environ, {"ZILLIZ_CLOUD_URI": "mocked_uri", "ZILLIZ_CLOUD_TOKEN": "mocked_token"})
    def test_init_without_uri(self):
        # Make sure it's not loaded from env
        try:
            del os.environ["ZILLIZ_CLOUD_URI"]
        except KeyError:
            pass
        # Test if an exception is raised when ZILLIZ_CLOUD_URI is missing
        with self.assertRaises(AttributeError):
            ZillizDBConfig()
            
    @mock.patch.dict(os.environ, {"ZILLIZ_CLOUD_URI": "mocked_uri", "ZILLIZ_CLOUD_TOKEN": "mocked_token"})
    def test_init_without_token(self):
        # Make sure it's not loaded from env
        try:
            del os.environ["ZILLIZ_CLOUD_TOKEN"]
        except KeyError:
            pass
        # Test if an exception is raised when ZILLIZ_CLOUD_TOKEN is missing
        with self.assertRaises(AttributeError):
            ZillizDBConfig()

    def test_init_invalid_cred(self):
        # Test if an exception is raised when provided invalid credentials
        with self.assertRaises(ValueError):
            uri = "ululululu"
            token = "random12345"
            config = ZillizDBConfig(uri=uri, token=token)
            ZillizVectorDB(config=config)


class TestZillizDBCollection(unittest.TestCase):
    @mock.patch.dict(os.environ, {"ZILLIZ_CLOUD_URI": "mocked_uri", "ZILLIZ_CLOUD_TOKEN": "mocked_token"})
    def test_init_with_default_collection(self):
        """
        Test if the `App` instance is initialized with the correct default collection name.
        """
        # Create a ZillizDBConfig instance
        db_config = ZillizDBConfig()

        self.assertEqual(db_config.collection_name, "embedchain_store")

    @mock.patch.dict(os.environ, {"ZILLIZ_CLOUD_URI": "mocked_uri", "ZILLIZ_CLOUD_TOKEN": "mocked_token"})
    def test_init_with_custom_collection(self):
        """
        Test if the `App` instance is initialized with the correct custom collection name.
        """
        # Create a ZillizDBConfig instance with mocked values

        expected_collection = "test_collection"
        db_config = ZillizDBConfig(collection_name='test_collection')

        self.assertEqual(db_config.collection_name, expected_collection)


if __name__ == "__main__":
    unittest.main()
