import hashlib
from io import StringIO
from urllib.parse import urlparse

import requests
import yaml

from embedchain.loaders.base_loader import BaseLoader


class OpenAPILoader(BaseLoader):
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
            return open(path)
        else:
            return open(content)

    @staticmethod
    def load_data(content):
        """Load yaml file of openapi. Each pair is a document."""
        data = []
        file_path = content
        data_content = []
        with OpenAPILoader._get_file_content(content=content) as file:
            yaml_data = yaml.load(file, Loader=yaml.SafeLoader)
            for i, (key, value) in enumerate(yaml_data.items()):
                string_data = f"{key}: {value}"
                metadata = {"url": file_path, "row": i + 1}
                data.append({"content": string_data, "meta_data": metadata})
                data_content.append(string_data)
        doc_id = hashlib.sha256((content + ", ".join(data_content)).encode()).hexdigest()
        return {"doc_id": doc_id, "data": data}
