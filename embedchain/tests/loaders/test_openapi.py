import pytest

from embedchain.loaders.openapi import OpenAPILoader


@pytest.fixture
def openapi_loader():
    return OpenAPILoader()


def test_load_data(openapi_loader, mocker):
    mocker.patch("builtins.open", mocker.mock_open(read_data="key1: value1\nkey2: value2"))

    mocker.patch("hashlib.sha256", return_value=mocker.Mock(hexdigest=lambda: "mock_hash"))

    file_path = "configs/openai_openapi.yaml"
    result = openapi_loader.load_data(file_path)

    expected_doc_id = "mock_hash"
    expected_data = [
        {"content": "key1: value1", "meta_data": {"url": file_path, "row": 1}},
        {"content": "key2: value2", "meta_data": {"url": file_path, "row": 2}},
    ]

    assert result["doc_id"] == expected_doc_id
    assert result["data"] == expected_data
