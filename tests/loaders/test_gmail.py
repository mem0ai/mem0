import pytest
from llama_hub.readwise.base import Document

from embedchain.loaders.gmail import GmailLoader


@pytest.fixture
def mock_quopri(mocker):
    return mocker.patch("embedchain.loaders.gmail.quopri.decodestring", return_value=b"your_test_decoded_string")


@pytest.fixture
def mock_beautifulsoup(mocker):
    return mocker.patch("embedchain.loaders.gmail.BeautifulSoup", return_value=mocker.MagicMock())


@pytest.fixture
def gmail_loader(mock_quopri, mock_beautifulsoup):
    return GmailLoader()


def test_load_data_file_not_found(gmail_loader, mocker):
    with pytest.raises(FileNotFoundError):
        with mocker.patch("os.path.isfile", return_value=False):
            gmail_loader.load_data("your_query")


@pytest.mark.skip(reason="TODO: Fix this test. Failing due to some googleapiclient import issue.")
def test_load_data(gmail_loader, mocker):
    mock_gmail_reader_instance = mocker.MagicMock()
    text = "your_test_email_text"
    metadata = {
        "id": "your_test_id",
        "snippet": "your_test_snippet",
    }
    mock_gmail_reader_instance.load_data.return_value = [Document(text=text, extra_info=metadata)]

    with mocker.patch("os.path.isfile", return_value=True):
        response_data = gmail_loader.load_data("your_query")

    assert "doc_id" in response_data
    assert "data" in response_data
    assert isinstance(response_data["doc_id"], str)
    assert isinstance(response_data["data"], list)
