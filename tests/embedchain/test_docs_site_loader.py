import unittest
from unittest.mock import MagicMock, patch

from embedchain.loaders.docs_site_loader import DocsSiteLoader


class TestDocsSiteLoader(unittest.TestCase):
    @patch("requests.get")
    def test_load_data(self, mock_get):
        """
        This test checks the functionality of the 'load_data' method in the DocsSiteLoader class.
        It verifies if the method can successfully extract a link from an HTML page
        and whether it returns a dictionary containing the expected keys and values.
        """
        html_data = "<html><body><a href='https://example.com/test-page'>Example</a></body></html>"
        mock_get.return_value = MagicMock(status_code=200, text=html_data, content=html_data.encode())

        loader = DocsSiteLoader()
        result = loader.load_data("https://example.com")

        self.assertIn("doc_id", result)
        self.assertIn("data", result)
        extracted_url = result["data"][0]["meta_data"]["url"]
        self.assertEqual(extracted_url, "https://example.com/test-page")
