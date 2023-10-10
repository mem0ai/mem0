import hashlib
from unittest.mock import Mock, patch

import pytest
from requests import Response

from embedchain.loaders.docs_site_loader import DocsSiteLoader


@pytest.fixture
def mock_requests_get():
    with patch("requests.get") as mock_get:
        yield mock_get


@pytest.fixture
def docs_site_loader():
    return DocsSiteLoader()


def test_get_child_links_recursive(mock_requests_get, docs_site_loader):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = """
        <html>
            <a href="/page1">Page 1</a>
            <a href="/page2">Page 2</a>
        </html>
    """
    mock_requests_get.return_value = mock_response

    docs_site_loader._get_child_links_recursive("https://example.com")

    assert len(docs_site_loader.visited_links) == 2
    assert "https://example.com/page1" in docs_site_loader.visited_links
    assert "https://example.com/page2" in docs_site_loader.visited_links


def test_get_child_links_recursive_status_not_200(mock_requests_get, docs_site_loader):
    mock_response = Mock()
    mock_response.status_code = 404
    mock_requests_get.return_value = mock_response

    docs_site_loader._get_child_links_recursive("https://example.com")

    assert len(docs_site_loader.visited_links) == 0


def test_get_all_urls(mock_requests_get, docs_site_loader):
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

    all_urls = docs_site_loader._get_all_urls("https://example.com")

    assert len(all_urls) == 3
    assert "https://example.com/page1" in all_urls
    assert "https://example.com/page2" in all_urls
    assert "https://example.com/external" in all_urls


def test_load_data_from_url(mock_requests_get, docs_site_loader):
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
    """.encode()
    mock_requests_get.return_value = mock_response

    data = docs_site_loader._load_data_from_url("https://example.com/page1")

    assert len(data) == 1
    assert data[0]["content"] == "Article Content"
    assert data[0]["meta_data"]["url"] == "https://example.com/page1"


def test_load_data_from_url_status_not_200(mock_requests_get, docs_site_loader):
    mock_response = Mock()
    mock_response.status_code = 404
    mock_requests_get.return_value = mock_response

    data = docs_site_loader._load_data_from_url("https://example.com/page1")

    assert data == []
    assert len(data) == 0


def test_load_data(mock_requests_get, docs_site_loader):
    mock_response = Response()
    mock_response.status_code = 200
    mock_response._content = """
        <html>
            <a href="/page1">Page 1</a>
            <a href="/page2">Page 2</a>
        """.encode()
    mock_requests_get.return_value = mock_response

    url = "https://example.com"
    data = docs_site_loader.load_data(url)
    expected_doc_id = hashlib.sha256((" ".join(docs_site_loader.visited_links) + url).encode()).hexdigest()

    assert len(data["data"]) == 2
    assert data["doc_id"] == expected_doc_id


def test_if_response_status_not_200(mock_requests_get, docs_site_loader):
    mock_response = Response()
    mock_response.status_code = 404
    mock_requests_get.return_value = mock_response

    url = "https://example.com"
    data = docs_site_loader.load_data(url)
    expected_doc_id = hashlib.sha256((" ".join(docs_site_loader.visited_links) + url).encode()).hexdigest()

    assert len(data["data"]) == 0
    assert data["doc_id"] == expected_doc_id
