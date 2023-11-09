import hashlib
import json
import os
import re

import requests

from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils import clean_string, is_valid_json_string

VALID_URL_PATTERN = "^https:\/\/[0-9A-z.]+.[0-9A-z.]+.[a-z]+\/.*\.json$"


class JSONLoader(BaseLoader):
    @staticmethod
    def _get_llama_hub_loader():
        try:
            from llama_hub.jsondata.base import \
                JSONDataReader as LLHUBJSONLoader
        except ImportError as e:
            raise Exception(
                f"Failed to install required packages: {e}, \
                install them using `pip install --upgrade 'embedchain[json]`"
            )

        return LLHUBJSONLoader()

    @staticmethod
    def _check_content(content):
        if not isinstance(content, str):
            raise ValueError(
                "Invaid content input. \
                If you want to upload (list, dict, etc.), do \
                    `json.dump(data, indent=0)` and add the stringified JSON. \
                        Check - `https://docs.embedchain.ai/data-sources/json`"
            )

    @staticmethod
    def load_data(content):
        """Load a json file. Each data point is a key value pair."""

        JSONLoader._check_content(content)
        loader = JSONLoader._get_llama_hub_loader()

        data = []
        data_content = []

        content_url_str = content

        # Load json data from various sources.
        if os.path.isfile(content):
            with open(content, "r", encoding="utf-8") as json_file:
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
        elif is_valid_json_string(content):
            json_data = content
            content_url_str = hashlib.sha256((content).encode("utf-8")).hexdigest()
        else:
            raise ValueError(f"Invalid content to load json data from: {content}")

        docs = loader.load_data(json_data)
        for doc in docs:
            doc_content = clean_string(doc.text)
            data.append({"content": doc_content, "meta_data": {"url": content_url_str}})
            data_content.append(doc_content)

        doc_id = hashlib.sha256((content_url_str + ", ".join(data_content)).encode()).hexdigest()
        return {"doc_id": doc_id, "data": data}
