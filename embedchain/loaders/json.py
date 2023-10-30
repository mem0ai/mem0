import hashlib
import json
import os
import re

import requests

from embedchain.loaders.base_loader import BaseLoader

VALID_URL_PATTERN = "^https:\/\/[0-9A-z.]+.[0-9A-z.]+.[a-z]+\/.*\.json$"


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

        if not isinstance(content, str):
            print(f"Invaid content input. Provide the correct path to the json file saved locally in {content}")

        data = []
        data_content = []

        # Load json data from various sources. TODO: add support for dictionary
        if os.path.isfile(content):
            with open(content, "r") as json_file:
                json_data = json.load(json_file)
        elif re.match(VALID_URL_PATTERN, content):
            response = requests.get(content)
            if response.status_code == 200:
                json_data = response.json()
            else:
                raise ValueError(
                    f"Loading data from the given url: {content} failed. \
                    Make sure the url is working."
                )
        else:
            raise ValueError(f"Invalid content to load json data from: {content}")

        docs = loader.load_data(json_data)
        for doc in docs:
            doc_content = doc.text
            data.append({"content": doc_content, "meta_data": {"url": content}})
            data_content.append(doc_content)
        doc_id = hashlib.sha256((content + ", ".join(data_content)).encode()).hexdigest()
        return {"doc_id": doc_id, "data": data}
