import hashlib
import unittest
from unittest.mock import Mock, patch

from embedchain.loaders.web_page import WebPageLoader


class TestWebPageLoader(unittest.TestCase):
    def setUp(self):
        self.loader = WebPageLoader()
        self.page_url = "https://example.com/page"

    @patch("embedchain.loaders.web_page.requests.get")
    def test_load_data(self, mock_requests_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = """
            <html>
                <head>
                    <title>Test Page</title>
                </head>
                <body>
                    <div id="content">
                        <p>This is some test content.</p>
                    </div>
                </body>
            </html>
        """
        mock_requests_get.return_value = mock_response

        result = self.loader.load_data(self.page_url)

        content = self.loader._get_clean_content(mock_response.content, self.page_url)
        expected_doc_id = hashlib.sha256((content + self.page_url).encode()).hexdigest()
        self.assertEqual(result["doc_id"], expected_doc_id)

        expected_data = [
            {
                "content": content,
                "meta_data": {
                    "url": self.page_url,
                },
            }
        ]

        self.assertEqual(result["data"], expected_data)

    def test_get_clean_content_excludes_unnecessary_info(self):
        loader = WebPageLoader()

        mock_html = """
            <html>
            <head>
                <title>Sample HTML</title>
                <style>
                    /* Stylesheet to be excluded */
                    .elementor-location-header {
                        background-color: #f0f0f0;
                    }
                </style>
            </head>
            <body>
                <header id="header">Header Content</header>
                <nav class="nav">Nav Content</nav>
                <aside>Aside Content</aside>
                <form>Form Content</form>
                <main>Main Content</main>
                <footer class="footer">Footer Content</footer>
                <script>Some Script</script>
                <noscript>NoScript Content</noscript>
                <svg>SVG Content</svg>
                <canvas>Canvas Content</canvas>
                
                <div id="sidebar">Sidebar Content</div>
                <div id="main-navigation">Main Navigation Content</div>
                <div id="menu-main-menu">Menu Main Menu Content</div>
                
                <div class="header-sidebar-wrapper">Header Sidebar Wrapper Content</div>
                <div class="blog-sidebar-wrapper">Blog Sidebar Wrapper Content</div>
                <div class="related-posts">Related Posts Content</div>
            </body>
            </html>
        """

        tags_to_exclude = [
            "nav",
            "aside",
            "form",
            "header",
            "noscript",
            "svg",
            "canvas",
            "footer",
            "script",
            "style",
        ]
        ids_to_exclude = ["sidebar", "main-navigation", "menu-main-menu"]
        classes_to_exclude = [
            "elementor-location-header",
            "navbar-header",
            "nav",
            "header-sidebar-wrapper",
            "blog-sidebar-wrapper",
            "related-posts",
        ]

        content = loader._get_clean_content(mock_html, self.page_url)

        for tag in tags_to_exclude:
            self.assertNotIn(tag, content)

        for id in ids_to_exclude:
            self.assertNotIn(id, content)

        for class_name in classes_to_exclude:
            self.assertNotIn(class_name, content)

        self.assertGreater(len(content), 0)
