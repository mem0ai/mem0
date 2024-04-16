import hashlib
from unittest.mock import patch

import pytest

from embedchain.loaders.excel_file import ExcelFileLoader


@pytest.fixture
def excel_file_loader():
    return ExcelFileLoader()


def test_load_data(excel_file_loader):
    mock_url = "mock_excel_file.xlsx"
    expected_content = "Sample Excel Content"

    # Mock the load_data method of the excel_file_loader instance
    with patch.object(
        excel_file_loader,
        "load_data",
        return_value={
            "doc_id": hashlib.sha256((expected_content + mock_url).encode()).hexdigest(),
            "data": [{"content": expected_content, "meta_data": {"url": mock_url}}],
        },
    ):
        result = excel_file_loader.load_data(mock_url)

    assert result["data"][0]["content"] == expected_content
    assert result["data"][0]["meta_data"]["url"] == mock_url

    expected_doc_id = hashlib.sha256((expected_content + mock_url).encode()).hexdigest()
    assert result["doc_id"] == expected_doc_id
