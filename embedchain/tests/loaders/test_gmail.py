import pytest

from embedchain.loaders.gmail import GmailLoader


@pytest.fixture
def mock_beautifulsoup(mocker):
    mock_soup = mocker.MagicMock()
    mock_soup.get_text.return_value = "Test email body content"
    return mocker.patch("embedchain.loaders.gmail.BeautifulSoup", return_value=mock_soup)


@pytest.fixture
def gmail_loader(mock_beautifulsoup):
    return GmailLoader()


def test_load_data_file_not_found(gmail_loader, mocker):
    with pytest.raises(FileNotFoundError):
        with mocker.patch("os.path.isfile", return_value=False):
            gmail_loader.load_data("your_query")


def test_load_data(gmail_loader, mocker):
    # Mock the GmailReader class and its methods
    mock_gmail_reader = mocker.patch("embedchain.loaders.gmail.GmailReader")
    mock_reader_instance = mocker.MagicMock()
    mock_gmail_reader.return_value = mock_reader_instance
    
    # Mock the email data that would be returned
    mock_emails = [
        {
            "subject": "Test Subject",
            "from": "test@example.com",
            "to": "recipient@example.com",
            "date": "2024-01-01T00:00:00",
            "body": "Test email body content"
        }
    ]
    mock_reader_instance.load_emails.return_value = mock_emails

    with mocker.patch("os.path.isfile", return_value=True):
        response_data = gmail_loader.load_data("your_query")

    assert "doc_id" in response_data
    assert "data" in response_data
    assert isinstance(response_data["doc_id"], str)
    assert isinstance(response_data["data"], list)
    assert len(response_data["data"]) == 1
    assert "content" in response_data["data"][0]
    assert "meta_data" in response_data["data"][0]
