from typing import Optional

from embedchain.config.vectordbs.BaseVectorDbConfig import BaseVectorDbConfig
from embedchain.helper.json_serializable import register_deserializable


@register_deserializable
class WeaviateDbConfig(BaseVectorDbConfig):
    def __init__(
        self,
        class_name: Optional[str] = None,
        class_schema: Optional[dict] = None,
        allow_reset=False,
    ):
        """
        Initializes a configuration class instance for Weaviate.

        :param class_name: Default name for the class of objects, defaults to None
        :type class_name: Optional[str], optional
        :param class_schema: Additional configurations like vectorizer, module_config, properties, etc.., defaults to None
        :type class_schema: Optional[dict], optional
        :param allow_reset: If resetting DB is allowed, default is False
        :type allow_reset: bool
        """

        class_schema["class_name"] = class_name
        self.class_schema = class_schema
        self.allow_reset = allow_reset
        super.__init__(class_name=class_name)
