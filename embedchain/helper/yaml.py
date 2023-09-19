import json
from typing import Dict

import yaml


def sanitize(data: Dict[str, str]) -> Dict[str, str]:
    """
    Optimize for human use by removing parts that are:
    1. duplicates
    2. hard to read
    3. redundant

    :param data: serialized json data
    :type data: Dict[str, str]
    :return: sanitized serialized json data
    :rtype: Dict[str, str]
    """
    # Session id should not be stored persistently
    del data["s_id"]

    # For most users, history should not be stored persistently.
    # I'm sure there are use-cases for this.
    if not data["llm"]["history"] or len(data["llm"]["history"]) == 0:
        del data["llm"]["history"]

    return data


class Yaml:
    def save(self, filename: str = "config.yaml"):
        data = json.loads(self.serialize())

        # Sanitize
        sanitized_data = sanitize(data)

        with open(filename, "w") as file:
            yaml.dump(sanitized_data, file, default_flow_style=False)
