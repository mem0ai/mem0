import json
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from embedchain.config import RedisDBConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.vectordb.base import BaseVectorDB

try:
    import redis
    from redis import Redis
    from redisvl.index import SearchIndex
    from redisvl.query import FilterQuery, VectorQuery
    from redisvl.query.filter import FilterExpression, Tag
    from redisvl.schema.schema import IndexSchema
    from redisvl.redis.utils import array_to_buffer
except ImportError as err:
    raise ImportError(
        f"{str(err)}: Redis requires extra dependencies. Install with `pip install --upgrade embedchain[redis]`"
    ) from None


@register_deserializable
class RedisDB(BaseVectorDB):
    """Vector database using RedisDB."""

    BATCH_SIZE: int = 500

    def __init__(self, config: Optional[RedisDBConfig] = None):
        """Initialize a new RedisDB instance
        :param config: Configuration options for Redis, defaults to None
        :type config: Optional[RedisDBConfig], optional
        """
        if config is None:
            self.config = RedisDBConfig()
        else:
            if not isinstance(config, RedisDBConfig):
                raise TypeError(
                    "config is not a `PineconeDBConfig` instance. "
                    "Please make sure the type is right and that you are passing an instance."
                )
            self.config = config
        try:
            logging.info(f"Connecting to Redis instance at {self.config.redis_url}")
            self.client = Redis.from_url(self.config.redis_url)
            self.client.ping()
        except redis.exceptions.ConnectionError as err:
            logging.exception(f"Error connection to Redis: {str(err)}")
            raise

        index_name = prefix = self._get_or_create_collection()

        # Setup metadata keys and tag fields in the base schema
        self._supported_metadata_keys = {"data_type", "doc_id", "url", "hash", "app_id"}
        self._metadata_json_path = f"$.{self.config.metadata_field_name}"

        # Setup schema for the index with fields
        self._schema = IndexSchema(
            index={"name": index_name, "prefix": prefix, "storage_type": "json"}
        )
        self._schema.add_fields(
            [
                {
                    "name": self.config.id_field_name,
                    "type": "tag",
                    "attrs": {"sortable": True}
                },
                {
                    "name": self.config.text_field_name,
                    "type": "text",
                    "attrs": {"sortable": True}
                },
            ]
        )
        for key in self._supported_metadata_keys:
            self._schema.add_field({
                "name": key,
                "path": f"$.{self.config.metadata_field_name}.{key}",
                "type": "tag",
                "attrs": {"sortable": True}
            })

        super().__init__(config=self.config)

    def _initialize(self):
        """This method is needed because `embedder` attribute needs to be set
        externally before it can be initialized.
        """
        if not self.embedder:
            raise ValueError(
                "Embedder not set. Please set an embedder with "
                "`set_embedder` before initialization."
            )

        index_name = self._get_or_create_collection()

        if self.config.vector_field_name not in self._schema.fields:
            # Build vector config for index schema
            vector_config = self.config.vector_config or {}
            vector_field = {
                "name": self.config.vector_field_name,
                "type": "vector",
                "attrs": {
                    **vector_config,
                    "dims": self.embedder.vector_dimension
                },
            }
            if "algorithm" not in vector_field["attrs"]:
                vector_field["attrs"]["algorithm"] = "hnsw"

            # Add vector field to schema based on config
            self._schema.add_field(vector_field)

        self._index = SearchIndex(self._schema, self.client)

        if not self._index.exists():
            logging.info(f"Creating new Redis index {index_name}")
            self._index.create()

    def _get_or_create_db(self):
        """Called during initialization"""
        return self.client

    def _get_or_create_collection(self) -> str:
        """Get the Redis index name for a collection
        :return: Redis index name
        :rtype: str
        """
        return self.config.collection_name

    def set_collection_name(self, name: str):
        """
        Set the name of the collection. A collection is an isolated space for vectors.

        :param name: Name of the collection.
        :type name: str
        """
        if not isinstance(name, str):
            raise TypeError("Collection name must be a string")
        self.config.collection_name = name

    def _build_metadata_filter(self, where: Optional[Dict[str, Any]] = None) -> FilterExpression:
        """
        Build a Redis filter expression from an embedchain where-clause
        """
        # subset metadata keys
        metadata_keys = self._supported_metadata_keys.intersection(set(where.keys() if where is not None else set()))
        # start with empty filter
        metadata_filter = FilterExpression("*")
        # iterate and build a complete filter expression
        for key in metadata_keys:
            if where[key]:
                metadata_filter = (metadata_filter) & (Tag(key) == where[key])
        return metadata_filter

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
        # Handle empty case
        if ids is None or len(ids) == 0:
            return {"ids": [], "metadatas": []}
        # Generate filter expression
        filters = (Tag(self.config.id_field_name) == ids) & (self._build_metadata_filter(where))
        # Build query to find matching records (up to limit)
        query = FilterQuery(
            filter_expression=filters, return_fields=[self.config.id_field_name, self._metadata_json_path]
        )
        if limit is not None:
            query.set_paging(0, limit)
        # Execute search
        try:
            response = self._index.query(query)
            return {
                "ids": [res[self.config.id_field_name] for res in response],
                "metadatas": [json.loads(res[self._metadata_json_path]) for res in response],
            }
        except redis.exceptions.RedisError as err:
            logging.exception(f"A Redis error occurred while querying: {str(err)}")
            raise

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
        # Preprocess data and write to Redis
        data: List[Dict[str, Any]] = []
        for id_val, text, metadata, embeddings in zip(ids, documents, metadatas, embeddings):
            data.append(
                {
                    self.config.id_field_name: id_val,
                    self.config.text_field_name: text,
                    self.config.metadata_field_name: metadata,
                    self.config.vector_field_name: embeddings,
                }
            )
        try:
            # Load dataset
            self._index.load(data=data, id_field=self.config.id_field_name, batch_size=self.BATCH_SIZE)
        except redis.exceptions.ResponseError as err:
            logging.exception(f"Error while loading data to Redis: {str(err)}")
            raise

    def query(
        self,
        input_query: list[str],
        n_results: int,
        where: dict[str, any],
        citations: bool = False,
        **kwargs: Optional[dict[str, Any]],
    ) -> Union[list[tuple[str, dict]], list[str]]:
        """
        query contents from vector database based on vector similarity
        :param input_query: list of query string
        :type input_query: list[str]
        :param n_results: no of similar documents to fetch from database
        :type n_results: int
        :param where: Optional. to filter data
        :type where: dict[str, any]
        :param citations: we use citations boolean param to return context along with the answer.
        :type citations: bool, default is False.
        :return: The content of the document that matched your query,
        along with url of the source and doc_id (if citations flag is true)
        :rtype: list[str], if citations=False, otherwise list[tuple[str, str, str]]
        """
        # Build embedding vector and query
        query_vector = array_to_buffer(self.embedder.embedding_fn([input_query])[0])
        query = VectorQuery(
            vector=query_vector,
            vector_field_name=self.config.vector_field_name,
            return_fields=[self.config.id_field_name, self.config.text_field_name, self._metadata_json_path],
            num_results=n_results,
            return_score=True,
        )
        # Handle filters and then search
        query.set_filter(self._build_metadata_filter(where))
        try:
            results = self._index.query(query)
            # Process query results
            contexts: Union[List[Tuple[str, Dict[str, Any]]], List[str]] = []
            for result in results:
                context = result[self.config.text_field_name]
                if citations:
                    metadata = json.loads(result[self._metadata_json_path])
                    metadata["score"] = result["vector_distance"]
                    contexts.append(tuple((context, metadata)))
                else:
                    contexts.append(context)
            return contexts
        except redis.exceptions.RedisError as err:
            logging.exception(f"A Redis error occurred while querying: {str(err)}")
            raise
        except Exception as err:
            logging.exception(f"An unexpected error occurred: {str(err)}")
            raise

    def count(self) -> int:
        """
        Count number of documents/chunks embedded in the database.
        :return: number of documents
        :rtype: int
        """
        result = self._index.info()
        return int(result["num_docs"])

    def delete(self, where: Dict[str, Any]):
        """Delete records from Redis based on a filter.
        :param where: to filter data
        :type where: dict[str, any]
        """
        # Fetch records that match the filter
        query = FilterQuery(
            filter_expression=self._build_metadata_filter(where), return_fields=[self.config.id_field_name]
        )
        # Delete in batches
        for batch in self._index.query_batch(query, batch_size=100):
            self.client.delete(*[item[self.config.id_field_name] for item in batch])
            logging.info(f"Deleted batch of {len(batch)} records from Redis")

    def reset(self):
        """
        Resets the database. Deletes all embeddings irreversibly.
        """
        try:
            self._index.delete(drop=True)
            logging.info("Redis index deleted")
        except Exception as err:
            logging.exception(f"An unexpected error occurred: {str(err)}")
            raise
