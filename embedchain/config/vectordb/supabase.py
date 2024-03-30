import os
from typing import Optional, Union

import vecs
from embedchain.config.vectordb.base import BaseVectorDbConfig
from embedchain.helpers.json_serializable import register_deserializable


@register_deserializable
class SupabaseDBConfig(BaseVectorDbConfig):
    def __init__(
        self,
        url: str,
        postgres_connection_string: Optional[str],
        collection_name: str,
        dimension: int,
        index_measure: str = vecs.IndexMeasure.cosine_distance,
        index_method: str = vecs.IndexMethod.hnsw,
        query_filters: Optional[dict[str, Union[str, int, bool]]] = None,
        **extra_params: dict[str, Union[str, int, bool]],
    ):
        self.url = url
        self.extra_params = extra_params
        self.postgres_connection_string = postgres_connection_string
        self.collection_name = collection_name
        self.dimension = dimension
        self.index_measure = index_measure
        self.index_method = index_method
        self.query_filters = query_filters

        """
        postgres_connection_string (str): it is of the form :
        "postgresql://<user>:<password>@<host>:<port>/<db_name>" and required to create a client
        """
        if self.postgres_connection_string is None:
            raise ValueError("postgres_connection_string is required to establish Database connection")

        super().__init__(url, dir=None)
