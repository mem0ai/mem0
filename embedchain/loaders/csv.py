import csv
import hashlib
from io import StringIO
from urllib.parse import urlparse

import requests

from embedchain.loaders.base_loader import BaseLoader


class CsvLoader(BaseLoader):
    @staticmethod
    def _detect_delimiter(first_line):
        delimiters = [",", "\t", ";", "|"]
        counts = {delimiter: first_line.count(delimiter) for delimiter in delimiters}
        return max(counts, key=counts.get)

    @staticmethod
    def _get_file_content(content):
        url = urlparse(content)
        if all([url.scheme, url.netloc]) and url.scheme not in ["file", "http", "https"]:
            raise ValueError("Not a valid URL.")

        if url.scheme in ["http", "https"]:
            response = requests.get(content)
            response.raise_for_status()
            return StringIO(response.text)
        elif url.scheme == "file":
            path = url.path
            return open(path, newline="")  # Open the file using the path from the URI
        else:
            return open(content, newline="")  # Treat content as a regular file path

    @staticmethod
    def load_data(content):
        """Load a csv file with headers. Each line is a document"""
        result = []
        lines = []
        with CsvLoader._get_file_content(content) as file:
            first_line = file.readline()
            delimiter = CsvLoader._detect_delimiter(first_line)
            file.seek(0)  # Reset the file pointer to the start
            reader = csv.DictReader(file, delimiter=delimiter)
            for i, row in enumerate(reader):
                line = ", ".join([f"{field}: {value}" for field, value in row.items()])
                lines.append(line)
                result.append({"content": line, "meta_data": {"url": content, "row": i + 1}})
        doc_id = hashlib.sha256((content + " ".join(lines)).encode()).hexdigest()
        return {"doc_id": doc_id, "data": result}
