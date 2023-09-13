import unittest

from embedchain.embedder.base import BaseEmbedder


class TestEmbedder(unittest.TestCase):
    def test_init_with_invalid_vector_dim(self):
        # Test if an exception is raised when an invalid vector_dim is provided
        embedder = BaseEmbedder()
        with self.assertRaises(TypeError):
            embedder.set_vector_dimension(None)
