import hashlib
import os
import unittest
from unittest.mock import MagicMock, patch

from embedchain.loaders.notion import NotionLoader


class TestNotionLoader(unittest.TestCase):
    @patch.dict(os.environ, {"NOTION_INTEGRATION_TOKEN": "test_notion_token"})
    def test_load_data(self):
        source = "https://www.notion.so/Test-Page-1234567890abcdef1234567890abcdef"
        mock_text = "This is a test page."
        expected_doc_id = hashlib.sha256((mock_text + source).encode()).hexdigest()
        expected_data = [
            {
                "content": mock_text,
                "meta_data": {"url": "notion-12345678-90ab-cdef-1234-567890abcdef"},  # formatted_id
            }
        ]

        mock_page = MagicMock()
        mock_page.text = mock_text
        mock_documents = [mock_page]

        with patch("embedchain.loaders.notion.NotionPageReader") as mock_reader:
            mock_reader.return_value.load_data.return_value = mock_documents
            loader = NotionLoader()
            result = loader.load_data(source)

        self.assertEqual(result["doc_id"], expected_doc_id)
        self.assertEqual(result["data"], expected_data)
