import hashlib
import json
import os
import re
from typing import Union

import requests

from embedchain.loaders.base_loader import BaseLoader
from embedchain.utils.misc import clean_string, is_valid_json_string


class JSONReader:
    def __init__(self) -> None:
        """Initialize the JSONReader."""
        pass

    @staticmethod
    def load_data(json_data: Union[dict, str]) -> list[str]:
        """Load data from a JSON structure.

        Args:
            json_data (Union[dict, str]): The JSON data to load.

        Returns:
            list[str]: A list of strings representing the leaf nodes of the JSON.
        """
        if isinstance(json_data, str):
            json_data = json.loads(json_data)
        else:
            json_data = json_data

        json_output = json.dumps(json_data, indent=0)
        lines = json_output.split("\n")
        useful_lines = [line for line in lines if not re.match(r"^[{}\[\],]*$", line)]
        return ["\n".join(useful_lines)]


VALID_URL_PATTERN = (
    "^https?://(?:www\.)?(?:\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|[a-zA-Z0-9.-]+)(?::\d+)?/(?:[^/\s]+/)*[^/\s]+\.json$"
)


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
            text = doc if isinstance(doc, str) else doc["text"]
            doc_content = clean_string(text)
            data.append({"content": doc_content, "meta_data": {"url": content_url_str}})
            data_content.append(doc_content)

        doc_id = hashlib.sha256((content_url_str + ", ".join(data_content)).encode()).hexdigest()
        return {"doc_id": doc_id, "data": data}
