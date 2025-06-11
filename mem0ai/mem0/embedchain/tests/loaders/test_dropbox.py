import os
from unittest.mock import MagicMock

import pytest
from dropbox.files import FileMetadata

from embedchain.loaders.dropbox import DropboxLoader


@pytest.fixture
def setup_dropbox_loader(mocker):
    mock_dropbox = mocker.patch("dropbox.Dropbox")
    mock_dbx = mocker.MagicMock()
    mock_dropbox.return_value = mock_dbx

    os.environ["DROPBOX_ACCESS_TOKEN"] = "test_token"
    loader = DropboxLoader()

    yield loader, mock_dbx

    if "DROPBOX_ACCESS_TOKEN" in os.environ:
        del os.environ["DROPBOX_ACCESS_TOKEN"]


def test_initialization(setup_dropbox_loader):
    """Test initialization of DropboxLoader."""
    loader, _ = setup_dropbox_loader
    assert loader is not None


def test_download_folder(setup_dropbox_loader, mocker):
    """Test downloading a folder."""
    loader, mock_dbx = setup_dropbox_loader
    mocker.patch("os.makedirs")
    mocker.patch("os.path.join", return_value="mock/path")

    mock_file_metadata = mocker.MagicMock(spec=FileMetadata)
    mock_dbx.files_list_folder.return_value.entries = [mock_file_metadata]

    entries = loader._download_folder("path/to/folder", "local_root")
    assert entries is not None


def test_generate_dir_id_from_all_paths(setup_dropbox_loader, mocker):
    """Test directory ID generation."""
    loader, mock_dbx = setup_dropbox_loader
    mock_file_metadata = mocker.MagicMock(spec=FileMetadata, name="file.txt")
    mock_dbx.files_list_folder.return_value.entries = [mock_file_metadata]

    dir_id = loader._generate_dir_id_from_all_paths("path/to/folder")
    assert dir_id is not None
    assert len(dir_id) == 64


def test_clean_directory(setup_dropbox_loader, mocker):
    """Test cleaning up a directory."""
    loader, _ = setup_dropbox_loader
    mocker.patch("os.listdir", return_value=["file1", "file2"])
    mocker.patch("os.remove")
    mocker.patch("os.rmdir")

    loader._clean_directory("path/to/folder")


def test_load_data(mocker, setup_dropbox_loader, tmp_path):
    loader = setup_dropbox_loader[0]

    mock_file_metadata = MagicMock(spec=FileMetadata, name="file.txt")
    mocker.patch.object(loader.dbx, "files_list_folder", return_value=MagicMock(entries=[mock_file_metadata]))
    mocker.patch.object(loader.dbx, "files_download_to_file")

    # Mock DirectoryLoader
    mock_data = {"data": "test_data"}
    mocker.patch("embedchain.loaders.directory_loader.DirectoryLoader.load_data", return_value=mock_data)

    test_dir = tmp_path / "dropbox_test"
    test_dir.mkdir()
    test_file = test_dir / "file.txt"
    test_file.write_text("dummy content")
    mocker.patch.object(loader, "_generate_dir_id_from_all_paths", return_value=str(test_dir))

    result = loader.load_data("path/to/folder")

    assert result == {"doc_id": mocker.ANY, "data": "test_data"}
    loader.dbx.files_list_folder.assert_called_once_with("path/to/folder")
