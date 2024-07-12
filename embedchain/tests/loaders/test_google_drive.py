import pytest

from embedchain.loaders.google_drive import GoogleDriveLoader


@pytest.fixture
def google_drive_folder_loader():
    return GoogleDriveLoader()


def test_load_data_invalid_drive_url(google_drive_folder_loader):
    mock_invalid_drive_url = "https://example.com"
    with pytest.raises(
        ValueError,
        match="The url provided https://example.com does not match a google drive folder url. Example "
        "drive url: https://drive.google.com/drive/u/0/folders/xxxx",
    ):
        google_drive_folder_loader.load_data(mock_invalid_drive_url)


@pytest.mark.skip(reason="This test won't work unless google api credentials are properly setup.")
def test_load_data_incorrect_drive_url(google_drive_folder_loader):
    mock_invalid_drive_url = "https://drive.google.com/drive/u/0/folders/xxxx"
    with pytest.raises(
        FileNotFoundError, match="Unable to locate folder or files, check provided drive URL and try again"
    ):
        google_drive_folder_loader.load_data(mock_invalid_drive_url)


@pytest.mark.skip(reason="This test won't work unless google api credentials are properly setup.")
def test_load_data(google_drive_folder_loader):
    mock_valid_url = "YOUR_VALID_URL"
    result = google_drive_folder_loader.load_data(mock_valid_url)
    assert "doc_id" in result
    assert "data" in result
    assert "content" in result["data"][0]
    assert "meta_data" in result["data"][0]
