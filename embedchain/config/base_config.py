from typing import Any

from embedchain.helpers.json_serializable import JSONSerializable


class BaseConfig(JSONSerializable):
    """
    Base config.
    """

    def __init__(self):
        """Initializes a configuration class for a class."""
        pass

    def as_dict(self) -> dict[str, Any]:
        """Return config object as a dict

        :return: config object as dict
        :rtype: dict[str, Any]
        """
        return vars(self)
