import hashlib
import unittest
from unittest.mock import mock_open, patch

from embedchain.loaders.mdx import MdxLoader


class TestMdxLoader(unittest.TestCase):
    def test_load_data(self):
        # Mock open function to simulate file reading
        mock_content = "Sample MDX Content"
        with patch("builtins.open", mock_open(read_data=mock_content)):
            loader = MdxLoader()

            url = "mock_file.mdx"
            result = loader.load_data(url)

            self.assertIn("doc_id", result)
            self.assertIn("data", result)

            self.assertEqual(result["data"][0]["content"], mock_content)

            self.assertEqual(result["data"][0]["meta_data"]["url"], url)

            expected_doc_id = hashlib.sha256((mock_content + url).encode()).hexdigest()

            self.assertEqual(result["doc_id"], expected_doc_id)
