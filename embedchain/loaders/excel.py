from embedchain.loaders.base_loader import BaseLoader
import pandas as pd
from io import StringIO
import os
import hashlib


class ExcelLoader(BaseLoader):
    @staticmethod
    def _convert_sheet_to_csv(file: str, sheet_name: str):
        """
        file: str
            Excel file location
        sheet_name: str
            Name of the Excel sheet
        """

        # Read the specified sheet from the Excel file
        temp_data = pd.read_excel(file, sheet_name=sheet_name)

        # Create buffer
        buffer = StringIO()

        # Convert to CSV and write to buffer
        temp_data.to_csv(buffer, index=False)

        # Get the CSV data as a string
        csv_string = buffer.getvalue()

        # Clean string
        csv_string = csv_string.replace("\r", "")

        csv_string = csv_string.strip("\n")

        return csv_string

    @staticmethod
    def load_data(content):
        """Load all sheets from an Excel file with headers. Each sheet is a document."""
        if not os.path.exists(content):
            raise FileNotFoundError(f"The file {content} does not exist.")

        # Create an ExcelFile object
        excel_file = pd.ExcelFile(content)

        # Initialize an empty list to store data from each sheet with metadata
        data_records = []

        # Initalize an empty list to store each sheet without metadata
        data_content = []

        # Iterate over all sheets in the Excel file
        for sheet_name in excel_file.sheet_names:
            # Get file into string for each sheet
            csv_string = ExcelLoader._convert_sheet_to_csv(file=content, sheet_name=sheet_name)

            # Create metadata for each sheet
            meta_data = {
                "url": content,
                "sheet_name": sheet_name,
                "file_size": os.path.getsize(content),
                "file_type": content.split(".")[-1],
            }

            # Append data for each sheet to the list
            data_records.append(
                {
                    "content": csv_string,
                    "meta_data": meta_data,
                }
            )

            data_content.append(csv_string)

        # Create doc_id for whole file
        doc_id = hashlib.sha256((content + "".join(data_content)).encode()).hexdigest()

        # Close the ExcelFile object
        excel_file.close()

        return {
            "doc_id": doc_id,  # You may want to use a common identifier for all sheets or choose another approach
            "data": data_records,
        }
