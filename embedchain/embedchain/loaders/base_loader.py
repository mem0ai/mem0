from typing import Any, Optional

from embedchain.helpers.json_serializable import JSONSerializable


class BaseLoader(JSONSerializable):
    def __init__(self):
        pass

    def load_data(self, url, **kwargs: Optional[dict[str, Any]]):
        """
        Implemented by child classes
        """
        pass
