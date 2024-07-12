import csv
import os
import pathlib
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from embedchain.loaders.csv import CsvLoader


@pytest.mark.parametrize("delimiter", [",", "\t", ";", "|"])
def test_load_data(delimiter):
    """
    Test csv loader

    Tests that file is loaded, metadata is correct and content is correct
    """
    # Creating temporary CSV file
    with tempfile.NamedTemporaryFile(mode="w+", newline="", delete=False) as tmpfile:
        writer = csv.writer(tmpfile, delimiter=delimiter)
        writer.writerow(["Name", "Age", "Occupation"])
        writer.writerow(["Alice", "28", "Engineer"])
        writer.writerow(["Bob", "35", "Doctor"])
        writer.writerow(["Charlie", "22", "Student"])

        tmpfile.seek(0)
        filename = tmpfile.name

        # Loading CSV using CsvLoader
        loader = CsvLoader()
        result = loader.load_data(filename)
        data = result["data"]

        # Assertions
        assert len(data) == 3
        assert data[0]["content"] == "Name: Alice, Age: 28, Occupation: Engineer"
        assert data[0]["meta_data"]["url"] == filename
        assert data[0]["meta_data"]["row"] == 1
        assert data[1]["content"] == "Name: Bob, Age: 35, Occupation: Doctor"
        assert data[1]["meta_data"]["url"] == filename
        assert data[1]["meta_data"]["row"] == 2
        assert data[2]["content"] == "Name: Charlie, Age: 22, Occupation: Student"
        assert data[2]["meta_data"]["url"] == filename
        assert data[2]["meta_data"]["row"] == 3

        # Cleaning up the temporary file
        os.unlink(filename)


@pytest.mark.parametrize("delimiter", [",", "\t", ";", "|"])
def test_load_data_with_file_uri(delimiter):
    """
    Test csv loader with file URI

    Tests that file is loaded, metadata is correct and content is correct
    """
    # Creating temporary CSV file
    with tempfile.NamedTemporaryFile(mode="w+", newline="", delete=False) as tmpfile:
        writer = csv.writer(tmpfile, delimiter=delimiter)
        writer.writerow(["Name", "Age", "Occupation"])
        writer.writerow(["Alice", "28", "Engineer"])
        writer.writerow(["Bob", "35", "Doctor"])
        writer.writerow(["Charlie", "22", "Student"])

        tmpfile.seek(0)
        filename = pathlib.Path(tmpfile.name).as_uri()  # Convert path to file URI

        # Loading CSV using CsvLoader
        loader = CsvLoader()
        result = loader.load_data(filename)
        data = result["data"]

        # Assertions
        assert len(data) == 3
        assert data[0]["content"] == "Name: Alice, Age: 28, Occupation: Engineer"
        assert data[0]["meta_data"]["url"] == filename
        assert data[0]["meta_data"]["row"] == 1
        assert data[1]["content"] == "Name: Bob, Age: 35, Occupation: Doctor"
        assert data[1]["meta_data"]["url"] == filename
        assert data[1]["meta_data"]["row"] == 2
        assert data[2]["content"] == "Name: Charlie, Age: 22, Occupation: Student"
        assert data[2]["meta_data"]["url"] == filename
        assert data[2]["meta_data"]["row"] == 3

        # Cleaning up the temporary file
        os.unlink(tmpfile.name)


@pytest.mark.parametrize("content", ["ftp://example.com", "sftp://example.com", "mailto://example.com"])
def test_get_file_content(content):
    with pytest.raises(ValueError):
        loader = CsvLoader()
        loader._get_file_content(content)


@pytest.mark.parametrize("content", ["http://example.com", "https://example.com"])
def test_get_file_content_http(content):
    """
    Test _get_file_content method of CsvLoader for http and https URLs
    """

    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.text = "Name,Age,Occupation\nAlice,28,Engineer\nBob,35,Doctor\nCharlie,22,Student"
        mock_get.return_value = mock_response

        loader = CsvLoader()
        file_content = loader._get_file_content(content)

        mock_get.assert_called_once_with(content)
        mock_response.raise_for_status.assert_called_once()
        assert file_content.read() == mock_response.text
