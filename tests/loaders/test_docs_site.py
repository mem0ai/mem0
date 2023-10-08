import hashlib
import unittest
from unittest.mock import Mock, patch

from requests import Response

from embedchain.loaders.docs_site_loader import DocsSiteLoader


class TestDocsSiteLoader(unittest.TestCase):
    def setUp(self):
        self.loader = DocsSiteLoader()

    @patch("requests.get")
    def test_get_child_links_recursive(self, mock_requests_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
            <html>
                <a href="/page1">Page 1</a>
                <a href="/page2">Page 2</a>
            </html>
        """
        mock_requests_get.return_value = mock_response

        self.loader._get_child_links_recursive("https://example.com")

        self.assertEqual(len(self.loader.visited_links), 2)
        self.assertTrue("https://example.com/page1" in self.loader.visited_links)
        self.assertTrue("https://example.com/page2" in self.loader.visited_links)

    @patch("requests.get")
    def test_get_child_links_recursive_status_not_200(self, mock_requests_get):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_requests_get.return_value = mock_response

        self.loader._get_child_links_recursive("https://example.com")

        self.assertEqual(len(self.loader.visited_links), 0)

    @patch("requests.get")
    def test_get_all_urls(self, mock_requests_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
            <html>
                <a href="/page1">Page 1</a>
                <a href="/page2">Page 2</a>
                <a href="https://example.com/external">External</a>
            </html>
        """
        mock_requests_get.return_value = mock_response

        all_urls = self.loader._get_all_urls("https://example.com")

        self.assertEqual(len(all_urls), 3)
        self.assertTrue("https://example.com/page1" in all_urls)
        self.assertTrue("https://example.com/page2" in all_urls)
        self.assertTrue("https://example.com/external" in all_urls)

    @patch("requests.get")
    def test_load_data_from_url(self, mock_requests_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = """
            <html>
                <nav>
                    <h1>Navigation</h1>
                </nav>
                <article class="bd-article">
                    <p>Article Content</p>
                </article>
            </html>
        """
        mock_requests_get.return_value = mock_response

        data = self.loader._load_data_from_url("https://example.com/page1")

        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["content"], "Article Content")
        self.assertEqual(data[0]["meta_data"]["url"], "https://example.com/page1")

    @patch("requests.get")
    def test_load_data_from_url_status_not_200(self, mock_requests_get):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_requests_get.return_value = mock_response

        data = self.loader._load_data_from_url("https://example.com/page1")

        self.assertEqual(data, [])
        self.assertEqual(len(data), 0)

    @patch("requests.get")
    def test_load_data(self, mock_requests_get):
        mock_response = Response()
        mock_response.status_code = 200
        mock_response._content = """
            <html>
                <a href="/page1">Page 1</a>
                <a href="/page2">Page 2</a>
            </html>
        """.encode()
        mock_requests_get.return_value = mock_response

        url = "https://example.com"
        data = self.loader.load_data(url)
        expected_doc_id = hashlib.sha256((" ".join(self.loader.visited_links) + url).encode()).hexdigest()

        self.assertEqual(len(data["data"]), 2)
        self.assertEqual(data["doc_id"], expected_doc_id)

    @patch("requests.get")
    def test_if_response_status_not_200(self, mock_requests_get):
        mock_response = Response()
        mock_response.status_code = 404
        mock_requests_get.return_value = mock_response

        url = "https://example.com"
        data = self.loader.load_data(url)
        expected_doc_id = hashlib.sha256((" ".join(self.loader.visited_links) + url).encode()).hexdigest()

        self.assertEqual(len(data["data"]), 0)
        self.assertEqual(data["doc_id"], expected_doc_id)
