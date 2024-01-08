import os
import tempfile
import pandas as pd
import pytest

from embedchain.loaders.excel import ExcelLoader


@pytest.fixture
def sample_excel_file():
    # Create a DataFrame for the first sheet
    df1 = pd.DataFrame(
        {"Name": ["Alice", "Bob", "Charlie"], "Age": [28, 35, 22], "Occupation": ["Engineer", "Doctor", "Student"]}
    )

    # Create a DataFrame for the second sheet with linked information
    df2 = pd.DataFrame(
        {"Name": ["David", "Eva", "Frank"], "Age": [40, 29, 33], "Occupation": ["Manager", "Engineer", "Teacher"]}
    )

    # Create a temporary Excel file with two sheets
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".xlsx", delete=False) as tmpfile:
        with pd.ExcelWriter(tmpfile.name, engine="openpyxl") as writer:
            df1.to_excel(writer, sheet_name="Sheet1", index=False)
            df2.to_excel(writer, sheet_name="LinkedSheet", index=False)

        # Save the workbook to enforce links between sheets
        writer.book.save(tmpfile.name)

    yield tmpfile.name

    # Clean up the temporary file
    os.unlink(tmpfile.name)


@pytest.mark.parametrize("sheet_name", ["Sheet1", "LinkedSheet"])
def test_load_data(sheet_name, sample_excel_file):
    """
    Test excel loader

    Tests that file is loaded, metadata is correct, and content is correct
    """
    # Loading Excel using ExcelLoader
    loader = ExcelLoader()
    result = loader.load_data(sample_excel_file)
    data = result["data"]

    # Assertions
    assert len(data) == 2

    assert data[0]["meta_data"]["url"] == sample_excel_file
    assert data[1]["meta_data"]["url"] == sample_excel_file

    assert data[0]["meta_data"]["sheet_name"] == "Sheet1"
    assert data[1]["meta_data"]["sheet_name"] == "LinkedSheet"

    assert data[0]["meta_data"]["file_size"] == os.path.getsize(sample_excel_file)
    assert data[1]["meta_data"]["file_size"] == os.path.getsize(sample_excel_file)

    assert data[0]["meta_data"]["file_type"] == "xlsx"
    assert data[1]["meta_data"]["file_type"] == "xlsx"

    assert data[0]["content"] == "Name,Age,Occupation\nAlice,28,Engineer\nBob,35,Doctor\nCharlie,22,Student"
    assert data[1]["content"] == "Name,Age,Occupation\nDavid,40,Manager\nEva,29,Engineer\nFrank,33,Teacher"
