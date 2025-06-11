import hashlib

import pytest

from embedchain.loaders.local_text import LocalTextLoader


@pytest.fixture
def text_loader():
    return LocalTextLoader()


def test_load_data(text_loader):
    mock_content = "This is a sample text content."

    result = text_loader.load_data(mock_content)

    assert "doc_id" in result
    assert "data" in result

    url = "local"
    assert result["data"][0]["content"] == mock_content

    assert result["data"][0]["meta_data"]["url"] == url

    expected_doc_id = hashlib.sha256((mock_content + url).encode()).hexdigest()
    assert result["doc_id"] == expected_doc_id
