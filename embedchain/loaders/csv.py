import csv

from embedchain.loaders.base_loader import BaseLoader

class CsvLoader(BaseLoader):
    def load_data(self, content):
        """Load a csv file wit headers. Each line is a document"""
        filename = content

        result = []

        with open(filename, newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for i, row in enumerate(reader):
                line = ", ".join([f"{field}: {value}" for field, value in row.items()])
                result.append({"content": line, "meta_data": {"url": filename, "row": i + 1}})

        return result
