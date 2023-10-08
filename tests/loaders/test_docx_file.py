import hashlib
import unittest
from unittest.mock import MagicMock, patch

from embedchain.loaders.docx_file import DocxFileLoader


class TestDocxFileLoader(unittest.TestCase):
    def test_load_data(self):
        loader = DocxFileLoader()

        mock_url = "mock_docx_file.docx"

        mock_loader = MagicMock()
        mock_loader.load.return_value = [MagicMock(page_content="Sample Docx Content", metadata={"url": "local"})]

        with patch("embedchain.loaders.docx_file.Docx2txtLoader", return_value=mock_loader):
            result = loader.load_data(mock_url)

            self.assertIn("doc_id", result)
            self.assertIn("data", result)

            expected_content = "Sample Docx Content"
            self.assertEqual(result["data"][0]["content"], expected_content)

            self.assertEqual(result["data"][0]["meta_data"]["url"], "local")

            expected_doc_id = hashlib.sha256((expected_content + mock_url).encode()).hexdigest()
            self.assertEqual(result["doc_id"], expected_doc_id)
