import hashlib
from unittest.mock import Mock, patch

import pytest
import requests

from embedchain.loaders.web_page import WebPageLoader


@pytest.fixture
def web_page_loader():
    return WebPageLoader()


def test_load_data(web_page_loader):
    page_url = "https://example.com/page"
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
    with patch("embedchain.loaders.web_page.WebPageLoader._session.get", return_value=mock_response):
        result = web_page_loader.load_data(page_url)

    content = web_page_loader._get_clean_content(mock_response.content, page_url)
    expected_doc_id = hashlib.sha256((content + page_url).encode()).hexdigest()
    assert result["doc_id"] == expected_doc_id

    expected_data = [
        {
            "content": content,
            "meta_data": {
                "url": page_url,
            },
        }
    ]

    assert result["data"] == expected_data


def test_get_clean_content_excludes_unnecessary_info(web_page_loader):
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

    content = web_page_loader._get_clean_content(mock_html, "https://example.com/page")

    for tag in tags_to_exclude:
        assert tag not in content

    for id in ids_to_exclude:
        assert id not in content

    for class_name in classes_to_exclude:
        assert class_name not in content

    assert len(content) > 0


def test_fetch_reference_links_success(web_page_loader):
    # Mock a successful response
    response = Mock(spec=requests.Response)
    response.status_code = 200
    response.content = b"""
    <html>
        <body>
            <a href="http://example.com">Example</a>
            <a href="https://another-example.com">Another Example</a>
            <a href="/relative-link">Relative Link</a>
        </body>
    </html>
    """

    expected_links = ["http://example.com", "https://another-example.com"]
    result = web_page_loader.fetch_reference_links(response)
    assert result == expected_links


def test_fetch_reference_links_failure(web_page_loader):
    # Mock a failed response
    response = Mock(spec=requests.Response)
    response.status_code = 404
    response.content = b""

    expected_links = []
    result = web_page_loader.fetch_reference_links(response)
    assert result == expected_links
