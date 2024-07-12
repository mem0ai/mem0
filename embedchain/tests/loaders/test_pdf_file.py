import pytest
from langchain.schema import Document


def test_load_data(loader, mocker):
    mocked_pypdfloader = mocker.patch("embedchain.loaders.pdf_file.PyPDFLoader")
    mocked_pypdfloader.return_value.load_and_split.return_value = [
        Document(page_content="Page 0 Content", metadata={"source": "example.pdf", "page": 0}),
        Document(page_content="Page 1 Content", metadata={"source": "example.pdf", "page": 1}),
    ]

    mock_sha256 = mocker.patch("embedchain.loaders.docs_site_loader.hashlib.sha256")
    doc_id = "mocked_hash"
    mock_sha256.return_value.hexdigest.return_value = doc_id

    result = loader.load_data("dummy_url")
    assert result["doc_id"] is doc_id
    assert result["data"] == [
        {"content": "Page 0 Content", "meta_data": {"source": "example.pdf", "page": 0, "url": "dummy_url"}},
        {"content": "Page 1 Content", "meta_data": {"source": "example.pdf", "page": 1, "url": "dummy_url"}},
    ]


def test_load_data_fails_to_find_data(loader, mocker):
    mocked_pypdfloader = mocker.patch("embedchain.loaders.pdf_file.PyPDFLoader")
    mocked_pypdfloader.return_value.load_and_split.return_value = []

    with pytest.raises(ValueError):
        loader.load_data("dummy_url")


@pytest.fixture
def loader():
    from embedchain.loaders.pdf_file import PdfFileLoader

    return PdfFileLoader()
