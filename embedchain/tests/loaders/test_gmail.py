import pytest

from embedchain.loaders.gmail import GmailLoader


@pytest.fixture
def mock_beautifulsoup(mocker):
    return mocker.patch("embedchain.loaders.gmail.BeautifulSoup", return_value=mocker.MagicMock())


@pytest.fixture
def gmail_loader(mock_beautifulsoup):
    return GmailLoader()


def test_load_data_file_not_found(gmail_loader, mocker):
    # We must patch GmailReader because its __init__ now checks dependencies
    # We simulate FileNotFoundError being raised by GmailReader (due to missing creds)
    with mocker.patch("embedchain.loaders.gmail.GmailReader", side_effect=FileNotFoundError):
        with pytest.raises(FileNotFoundError):
             gmail_loader.load_data("your_query")


def test_load_data(gmail_loader, mocker, mock_beautifulsoup):
    mock_gmail_reader_instance = mocker.MagicMock()
    text = "your_test_email_text"
    metadata = {
        "id": "your_test_id",
        "snippet": "your_test_snippet",
    }
    
    # Configure the BS4 mock to return the text string
    # mock_beautifulsoup is the class mock. The instance is its return value.
    # The instance's get_text() should return the string.
    mock_beautifulsoup.return_value.get_text.return_value = text

    mock_gmail_reader_instance.load_emails.return_value = [
        {
            "body": "<html><body>some html</body></html>", 
            "from": "sender",
            "to": "receiver",
            "subject": "subject",
            "date": "2023-01-01",
        }
    ]
    
    with mocker.patch("embedchain.loaders.gmail.GmailReader", return_value=mock_gmail_reader_instance):
        with mocker.patch("os.path.isfile", return_value=True):
            response_data = gmail_loader.load_data("your_query")

    assert "doc_id" in response_data
    assert "data" in response_data
    assert isinstance(response_data["doc_id"], str)
    assert isinstance(response_data["data"], list)
