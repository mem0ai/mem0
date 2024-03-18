import os
from typing import Optional, Union

from embedchain.config.vectordb.base import BaseVectorDbConfig
from embedchain.helpers.json_serializable import register_deserializable


@register_deserializable
class SupabaseDBConfig(BaseVectorDbConfig):
    def __init__(
        self,
        url: str,
        api_key: str,
        **extra_params: dict[str, Union[str, int, bool]],
    ):
        self.url = url
        self.api_key = api_key
        self.extra_params = extra_params

        super().__init__(url, api_key, dir=None)
