import os 
import unittest

from embedchain.config import LanceDBConfig
from embedchain.vectordb.lancedb import LanceDB


class TestLDB(unittest.TestCase):
    def setUp(self):
        self.ld_config = LanceDBConfig(uri="./mock_lancedb")

    def test_init_without_uri(self):
        #test if an exception is raised when an invalid config is provided
        with self.assertRaises(AttributeError):
            LanceDB()

    def test_init_with_invalid_ld_config(self):
        # test if an exception is raised when an invalid ld_config is provided
        with self.assertRaises(TypeError):
            LanceDB(config={"uri": "some_uri", "valid config": False})
