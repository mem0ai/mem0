import csv
import os
import pathlib
import tempfile

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
