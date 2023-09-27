import os 
import unittest

from embedchain.config import LanceDBConfig
from embedchain.vectordb.lancedb import LanceDB


class TestLDB(unittest.TestCase):
    def setUp(self):
        self.ld_config = LanceDBConfig(ld_uri="./mock_lancedb")
        self.vector_dim = 384

    def test_init_without_uri(self):
        #make sure it's not loaded from env
        try:
            del os.environ['LANCEDB_URI']
        except KeyError:
            pass 
        #test if an exception is raised when an invalid ld_config is provided
        with self.assertRaises(AttributeError):
            LanceDB()

    def test_init_with_invalid_ld_config(self):
        # test if an exception is raised when an invalid ld_config is provided
        with self.assertRaises(TypeError):
            LanceDB(ld_config={"LD_URI": "some_uri", "valid ld_config": False})
