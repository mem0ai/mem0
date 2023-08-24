import csv
import os
import tempfile

from embedchain.loaders.csv import \
    CsvLoader  # Change this to the appropriate import path


def test_load_data():
    """
    Test csv loader

    Tests that file is loaded, metadata is correct and content is correct
    """
    # Creating temporary CSV file
    with tempfile.NamedTemporaryFile(mode="w+", newline="", delete=False) as tmpfile:
        writer = csv.writer(tmpfile)
        writer.writerow(["Name", "Age", "Occupation"])
        writer.writerow(["Alice", "28", "Engineer"])
        writer.writerow(["Bob", "35", "Doctor"])
        writer.writerow(["Charlie", "22", "Student"])

        tmpfile.seek(0)
        filename = tmpfile.name

        # Loading CSV using CsvLoader
        loader = CsvLoader()
        result = loader.load_data(filename)

        # Assertions
        assert len(result) == 3
        assert result[0]["content"] == "Name: Alice, Age: 28, Occupation: Engineer"
        assert result[0]["meta_data"]["url"] == filename
        assert result[0]["meta_data"]["row"] == 1
        assert result[1]["content"] == "Name: Bob, Age: 35, Occupation: Doctor"
        assert result[1]["meta_data"]["url"] == filename
        assert result[1]["meta_data"]["row"] == 2
        assert result[2]["content"] == "Name: Charlie, Age: 22, Occupation: Student"
        assert result[2]["meta_data"]["url"] == filename
        assert result[2]["meta_data"]["row"] == 3

        # Cleaning up the temporary file
        os.unlink(filename)
