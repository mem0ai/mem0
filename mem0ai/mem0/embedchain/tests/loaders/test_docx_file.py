import hashlib
from unittest.mock import MagicMock, patch

import pytest

from embedchain.loaders.docx_file import DocxFileLoader


@pytest.fixture
def mock_docx2txt_loader():
    with patch("embedchain.loaders.docx_file.Docx2txtLoader") as mock_loader:
        yield mock_loader


@pytest.fixture
def docx_file_loader():
    return DocxFileLoader()


def test_load_data(mock_docx2txt_loader, docx_file_loader):
    mock_url = "mock_docx_file.docx"

    mock_loader = MagicMock()
    mock_loader.load.return_value = [MagicMock(page_content="Sample Docx Content", metadata={"url": "local"})]

    mock_docx2txt_loader.return_value = mock_loader

    result = docx_file_loader.load_data(mock_url)

    assert "doc_id" in result
    assert "data" in result

    expected_content = "Sample Docx Content"
    assert result["data"][0]["content"] == expected_content

    assert result["data"][0]["meta_data"]["url"] == "local"

    expected_doc_id = hashlib.sha256((expected_content + mock_url).encode()).hexdigest()
    assert result["doc_id"] == expected_doc_id
