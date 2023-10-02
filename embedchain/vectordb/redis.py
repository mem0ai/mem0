import logging
from json import dumps
from typing import Any, Dict, List, Optional

import numpy as np

from embedchain.config import RedisDBConfig
from embedchain.helper.json_serializable import register_deserializable
from embedchain.vectordb.base import BaseVectorDB

try:
    import redis
    from redis import Redis
    from redis.commands.search.field import TextField, VectorField
    from redis.commands.search.indexDefinition import IndexDefinition, IndexType
    from redis.commands.search.query import Query
except ImportError:
    raise ImportError(
        "Redis requires extra dependencies. Install with `pip install --upgrade embedchain[redis]`"
    ) from None


@register_deserializable
class RedisDB(BaseVectorDB):
    """Vector database using RedisDB."""

    def __init__(self, config: RedisDBConfig):
        """Initialize a new RedisDB instance

        :param config: Configuration options for Redis, defaults to None
        :type config: Optional[RedisDBConfig], optional
        """
        if config is None:
            raise ValueError("RedisDBConfig is required")

        self.config = config

        logging.info(f"Connecting to RedisDB server: {self.config.host}:{self.config.port}")

        self.client = Redis(
            host=self.config.host,
            port=self.config.port,
            password=self.config.password,
            db=self.config.db,
            decode_responses=self.config.decoded_response,
            username=self.config.user_name,
        )
        super().__init__(config=self.config)

    def _initialize(self):
        logging.info(self.client.info())
        index_name = self._get_index()

        try:
            self.client.ft(index_name).info()
            logging.info("Index already exists!")
        except redis.exceptions.ResponseError as err:
            logging.info(f"Index not found {index_name}, Error Msg: {err}")
            schema = (
                TextField("ids"),
                TextField("text"),
                TextField("metadata"),
                VectorField(
                    "embeddings",
                    "HNSW",
                    {
                        "TYPE": "FLOAT64",
                        "DIM": self.config.vector_dimension,
                        "DISTANCE_METRIC": "COSINE",
                    },
                ),
            )

            definition = IndexDefinition(prefix=[index_name], index_type=IndexType.HASH)
            self.client.ft(index_name).create_index(fields=schema, definition=definition)

    def _get_or_create_db(self):
        """Called during initialization"""
        return self.client

    def _get_index(self) -> str:
        """Get the Redis index for a collection

        :return: Redis index
        :rtype: str
        """

        return self.config.collection_name

    def __get_or_create_collection(self, name):
        """Note: nothing to return here. Discuss later"""

    def get(self, ids: Optional[List[str]] = None, where: Optional[Dict[str, any]] = None, limit: Optional[int] = None):
        """
        Get existing doc ids present in vector database

        :param ids: _list of doc ids to check for existence
        :type ids: List[str]
        :param where: to filter data
        :type where: Dict[str, any]
        :return: ids
        :type: Set[str]
        """

        if ids is None or len(ids) == 0:
            return {"ids": []}

        query = f"@ids:({'|'.join(ids)})"
        filter_conditions = " ".join([f"@{k}:({'|'.join(where[k])})" for k in where.keys() if len(where[k]) != 0])
        query = Query(query + filter_conditions).return_field("ids")

        if limit is not None:
            query.paging(0, limit)

        try:
            response = self.client.ft(self._get_index()).search(query=query).docs
            return {"ids": [x.ids for x in response]}
        except redis.exceptions.ResponseError as err:
            logging.info(f"Error :: {err}")
            return {"ids": {}}

    def add(self, documents: List[str], metadatas: List[object], ids: List[str]) -> Any:
        """
        Add vectors to Redis database

        :param documents: Documents
        :type documents: List[str]
        :param metadatas: Metadatas
        :type metadatas: List[object]
        :param ids: ids
        :type ids: List[str]
        """

        embeddings = self.embedder.embedding_fn(documents)
        pipeline = self.client.pipeline()

        for id_val, text, metadata, embeddings in zip(ids, documents, metadatas, embeddings):
            key = f"{self._get_index()}:{id_val}"
            value = {
                "ids": id_val,
                "text": text,
                "metadata": dumps(metadata),
                "embeddings": np.array(embeddings, dtype=np.float64).tobytes(),
            }
            pipeline.hset(key, mapping=value)

        pipeline.execute()

    def query(self, input_query: List[str], n_results: int, where: Dict[str, Any]) -> List[str]:
        """
        Query contents from vector data base based on vector similarity

        :param input_query: list of query string
        :type input_query: List[str]
        :param n_results: no of similar documents to fetch from database
        :type n_results: int
        :param where: to filter data
        :type where: Dict[str, Any]
        :return: The content of the document that matched your query.
        :rtype: List[str]
        """

        embedding_list = [np.array(row, dtype=np.float64).tobytes() for row in self.embedder.embedding_fn(input_query)]
        query_str = f"(*)=>[KNN {self.count()} @embeddings $vec as score]"
        filter_conditions = " ".join([f"@{k}:({'|'.join(where[k])})" for k in where.keys() if len(where[k]) != 0])
        if filter_conditions != "":
            query_str += " " + filter_conditions
        result = set()

        for embedding in embedding_list:
            query = Query(query_str).sort_by("score").return_fields("text", "score").dialect(2)

            query_params = {"vec": embedding}
            result.update(
                [
                    (resp.text, resp.score)
                    for resp in self.client.ft(index_name=self._get_index())
                    .search(query=query, query_params=query_params)
                    .docs
                ]
            )

        return [res[0] for res in sorted(list(result), key=lambda x: x[1])[:n_results]]

    def count(self) -> int:
        """
        Count number of documents/chunks embedded in the database.

        :return: number of documents
        :rtype: int
        """

        result = self.client.ft(self._get_index()).info()
        return int(result["num_docs"])

    def reset(self):
        """
        Resets the database. Deletes all embeddings irreversibly.
        """
        try:
            self.client.flushdb()

        except redis.exceptions.RedisError as e:
            logging.error(f"Redis Error: {str(e)}")

        except Exception as e:
            logging.error(f"An unexpected error occurred: {str(e)}")
