import csv

from embedchain.loaders.base_loader import BaseLoader


class CsvLoader(BaseLoader):
    def detect_delimiter(self, filename):
        with open(filename, 'r') as file:
            first_line = file.readline()
            delimiters = [',', '\t', ';', '|']
            counts = {delimiter: first_line.count(delimiter) for delimiter in delimiters}
            return max(counts, key=counts.get)
        
    def load_data(self, content):
        """Load a csv file wit headers. Each line is a document"""
        filename = content

        result = []

        with open(filename, newline="") as csvfile:
            reader = csv.DictReader(csvfile, delimiter=self.detect_delimiter(filename))
            for i, row in enumerate(reader):
                line = ", ".join([f"{field}: {value}" for field, value in row.items()])
                result.append({"content": line, "meta_data": {"url": filename, "row": i + 1}})

        return result
