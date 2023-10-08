import hashlib
import unittest

from embedchain.loaders.local_text import LocalTextLoader


class TestLocalTextLoader(unittest.TestCase):
    def test_load_data(self):
        loader = LocalTextLoader()

        mock_content = "This is a sample text content."

        result = loader.load_data(mock_content)

        self.assertIn("doc_id", result)
        self.assertIn("data", result)

        url = "local"
        self.assertEqual(result["data"][0]["content"], mock_content)

        self.assertEqual(result["data"][0]["meta_data"]["url"], url)

        expected_doc_id = hashlib.sha256((mock_content + url).encode()).hexdigest()
        self.assertEqual(result["doc_id"], expected_doc_id)
