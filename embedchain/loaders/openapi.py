import hashlib

import yaml

from embedchain.loaders.base_loader import BaseLoader


class OpenAPILoader(BaseLoader):
    @staticmethod
    def load_data(content):
        """Load yaml file of openapi. Each pair is a document."""
        data = []
        file_path = content
        with open(file_path, "r") as file:
            yaml_data = yaml.load(file, Loader=yaml.Loader)
            for i, (key, value) in enumerate(yaml_data.items()):
                content_data = f"{key}: {value}"
                meta_data = {"url": file_path, "row": i + 1}
                data.append({"content": content_data, "meta_data": meta_data})
        doc_id = hashlib.sha256((content + content_data).encode()).hexdigest()
        return {"doc_id": doc_id, "data": data}
