import hashlib
import json
import os
import re
from typing import Dict, List

import requests

from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils import clean_string, is_valid_json_string


class JSONReader:
    def __init__(self) -> None:
        """Initialize the JSONReader."""
        pass

    def _depth_first_traversal(self, json_data: Dict, path: List[str]) -> List[str]:
        """Perform a depth-first traversal of the JSON structure.

        Args:
            json_data (Dict): The JSON data to traverse.
            path (List[str]): The current path in the JSON structure.

        Returns:
            List[str]: A list of strings representing paths to the leaf nodes.
        """
        if isinstance(json_data, dict):
            for key, value in json_data.items():
                new_path = path + [key]
                yield from self._depth_first_traversal(value, new_path)
        elif isinstance(json_data, list):
            for item in json_data:
                yield from self._depth_first_traversal(item, path)
        else:
            yield " ".join(path + [str(json_data)])

    def load_data(self, json_data: Dict) -> List[str]:
        """Load data from a JSON structure.

        Args:
            json_data (Dict): The JSON data to load.

        Returns:
            List[str]: A list of strings representing the leaf nodes of the JSON.
        """
        if isinstance(json_data, str):
            json_data = json.loads(json_data)

        return list(self._depth_first_traversal(json_data, []))


VALID_URL_PATTERN = "^https:\/\/[0-9A-z.]+.[0-9A-z.]+.[a-z]+\/.*\.json$"


class JSONLoader(BaseLoader):
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
        loader = JSONReader()

        data = []
        data_content = []

        content_url_str = content

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
