import hashlib
import os
import sys
from unittest.mock import mock_open, patch

import pytest

if sys.version_info > (3, 10):  # as `match` statement was introduced in python 3.10
    from deepgram import PrerecordedOptions

    from embedchain.loaders.audio import AudioLoader


@pytest.fixture
def setup_audio_loader(mocker):
    mock_dropbox = mocker.patch("deepgram.DeepgramClient")
    mock_dbx = mocker.MagicMock()
    mock_dropbox.return_value = mock_dbx

    os.environ["DEEPGRAM_API_KEY"] = "test_key"
    loader = AudioLoader()
    loader.client = mock_dbx

    yield loader, mock_dbx

    if "DEEPGRAM_API_KEY" in os.environ:
        del os.environ["DEEPGRAM_API_KEY"]


@pytest.mark.skipif(
    sys.version_info < (3, 10), reason="Test skipped for Python 3.9 or lower"
)  # as `match` statement was introduced in python 3.10
def test_initialization(setup_audio_loader):
    """Test initialization of AudioLoader."""
    loader, _ = setup_audio_loader
    assert loader is not None


@pytest.mark.skipif(
    sys.version_info < (3, 10), reason="Test skipped for Python 3.9 or lower"
)  # as `match` statement was introduced in python 3.10
def test_load_data_from_url(setup_audio_loader):
    loader, mock_dbx = setup_audio_loader
    url = "https://example.com/audio.mp3"
    expected_content = "This is a test audio transcript."

    mock_response = {"results": {"channels": [{"alternatives": [{"transcript": expected_content}]}]}}
    mock_dbx.listen.prerecorded.v.return_value.transcribe_url.return_value = mock_response

    result = loader.load_data(url)

    doc_id = hashlib.sha256((expected_content + url).encode()).hexdigest()
    expected_result = {
        "doc_id": doc_id,
        "data": [
            {
                "content": expected_content,
                "meta_data": {"url": url},
            }
        ],
    }

    assert result == expected_result
    mock_dbx.listen.prerecorded.v.assert_called_once_with("1")
    mock_dbx.listen.prerecorded.v.return_value.transcribe_url.assert_called_once_with(
        {"url": url}, PrerecordedOptions(model="nova-2", smart_format=True)
    )


@pytest.mark.skipif(
    sys.version_info < (3, 10), reason="Test skipped for Python 3.9 or lower"
)  # as `match` statement was introduced in python 3.10
def test_load_data_from_file(setup_audio_loader):
    loader, mock_dbx = setup_audio_loader
    file_path = "local_audio.mp3"
    expected_content = "This is a test audio transcript."

    mock_response = {"results": {"channels": [{"alternatives": [{"transcript": expected_content}]}]}}
    mock_dbx.listen.prerecorded.v.return_value.transcribe_file.return_value = mock_response

    # Mock the file reading functionality
    with patch("builtins.open", mock_open(read_data=b"some data")) as mock_file:
        result = loader.load_data(file_path)

    doc_id = hashlib.sha256((expected_content + file_path).encode()).hexdigest()
    expected_result = {
        "doc_id": doc_id,
        "data": [
            {
                "content": expected_content,
                "meta_data": {"url": file_path},
            }
        ],
    }

    assert result == expected_result
    mock_dbx.listen.prerecorded.v.assert_called_once_with("1")
    mock_dbx.listen.prerecorded.v.return_value.transcribe_file.assert_called_once_with(
        {"buffer": mock_file.return_value}, PrerecordedOptions(model="nova-2", smart_format=True)
    )
