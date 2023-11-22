import os
from typing import Optional

from embedchain.config.vectordb.base import BaseVectorDbConfig
from embedchain.helpers.json_serializable import register_deserializable


@register_deserializable
class ZillizDBConfig(BaseVectorDbConfig):
    def __init__(
        self,
        collection_name: Optional[str] = None,
        dir: Optional[str] = None,
        uri: Optional[str] = None,
        token: Optional[str] = None,
        vector_dim: Optional[str] = None,
        metric_type: Optional[str] = None,
    ):
        """
        Initializes a configuration class instance for the vector database.

        :param collection_name: Default name for the collection, defaults to None
        :type collection_name: Optional[str], optional
        :param dir: Path to the database directory, where the database is stored, defaults to "db"
        :type dir: str, optional
        :param uri: Cluster endpoint obtained from the Zilliz Console, defaults to None
        :type uri: Optional[str], optional
        :param token: API Key, if a Serverless Cluster, username:password, if a Dedicated Cluster, defaults to None
        :type port: Optional[str], optional
        """
        self.uri = uri or os.environ.get("ZILLIZ_CLOUD_URI")
        if not self.uri:
            raise AttributeError(
                "Zilliz needs a URI attribute, "
                "this can either be passed to `ZILLIZ_CLOUD_URI` or as `ZILLIZ_CLOUD_URI` in `.env`"
            )

        self.token = token or os.environ.get("ZILLIZ_CLOUD_TOKEN")
        if not self.token:
            raise AttributeError(
                "Zilliz needs a token attribute, "
                "this can either be passed to `ZILLIZ_CLOUD_TOKEN` or as `ZILLIZ_CLOUD_TOKEN` in `.env`,"
                "if having a username and password, pass it in the form 'username:password' to `ZILLIZ_CLOUD_TOKEN`"
            )

        self.metric_type = metric_type if metric_type else "L2"

        self.vector_dim = vector_dim
        super().__init__(collection_name=collection_name, dir=dir)
