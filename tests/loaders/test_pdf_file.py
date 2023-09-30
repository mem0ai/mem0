import unittest
from unittest.mock import MagicMock, patch
from embedchain.loaders.pdf_file import PdfFileLoader

class TestPdfFileLoader(unittest.TestCase):
    @patch("embedchain.loaders.pdf_file.PyPDFLoader")
    def test_load_data(self, mock_PyPDFLoader):
        """
        Test the 'load_data' method of the PdfFileLoader class.

        This test checks if the 'load_data' method can successfully load data from a PDF file
        and return the expected structure.

        It mocks the PyPDFLoader class to simulate the loading of PDF content and metadata.

        """
        mock_loader_instance = mock_PyPDFLoader.return_value
        mock_loader_instance.load_and_split.return_value = [
            MagicMock(page_content="Page 1 Content", metadata={"page_num": 1}),
            MagicMock(page_content="Page 2 Content", metadata={"page_num": 2}),
        ]

        loader = PdfFileLoader()

        result = loader.load_data("https://example.com/test.pdf")

        self.assertIn("doc_id", result)
        self.assertIn("data", result)
        self.assertEqual(len(result["data"]), 2)
        self.assertEqual(result["data"][0]["content"], "Page 1 Content")
        self.assertEqual(result["data"][0]["meta_data"]["page_num"], 1)
        self.assertEqual(result["data"][1]["content"], "Page 2 Content")
        self.assertEqual(result["data"][1]["meta_data"]["page_num"], 2)
