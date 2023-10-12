import hashlib
from unittest.mock import mock_open, patch

import pytest

from embedchain.loaders.mdx import MdxLoader


@pytest.fixture
def mdx_loader():
    return MdxLoader()


def test_load_data(mdx_loader):
    mock_content = "Sample MDX Content"

    # Mock open function to simulate file reading
    with patch("builtins.open", mock_open(read_data=mock_content)):
        url = "mock_file.mdx"
        result = mdx_loader.load_data(url)

        assert "doc_id" in result
        assert "data" in result

        assert result["data"][0]["content"] == mock_content

        assert result["data"][0]["meta_data"]["url"] == url

        expected_doc_id = hashlib.sha256((mock_content + url).encode()).hexdigest()
        assert result["doc_id"] == expected_doc_id
