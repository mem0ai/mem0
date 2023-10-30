import hashlib
import json
import os

from embedchain.loaders.base_loader import BaseLoader


class JSONLoader(BaseLoader):
    @staticmethod
    def load_data(content):
        """Load a json file. Each data point is a key value pair."""
        try:
            from llama_hub.jsondata.base import \
                JSONDataReader as LLHBUBJSONLoader
        except ImportError:
            raise Exception(
                f"Couldn't import the required packages to load {content}, \
                Do `pip install --upgrade 'embedchain[json]`"
            )

        loader = LLHBUBJSONLoader()

        if not isinstance(content, str) and not os.path.isfile(content):
            print(f"Invaid content input. Provide the correct path to the json file saved locally in {content}")

        data = []
        data_content = []

        with open(content, "r") as json_file:
            json_data = json.load(json_file)
            docs = loader.load_data(json_data)
            for doc in docs:
                doc_content = doc.text
                data.append({"content": doc_content, "meta_data": {"url": content}})
                data_content.append(doc_content)
        doc_id = hashlib.sha256((content + ", ".join(data_content)).encode()).hexdigest()
        return {"doc_id": doc_id, "data": data}
