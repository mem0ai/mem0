from typing import Dict, List, Optional

from embedchain.config import ZillizDBConfig
from embedchain.helper.json_serializable import register_deserializable
from embedchain.vectordb.base import BaseVectorDB

try:
    from pymilvus import MilvusClient
    from pymilvus import connections, FieldSchema, CollectionSchema, DataType, Collection, utility
except ImportError:
    raise ImportError(
        "Zilliz requires extra dependencies. Install with `pip install --upgrade embedchain[pymilvus]`"
    ) from None


@register_deserializable
class ZillizVectorDB(BaseVectorDB):
    """Base class for vector database."""

    def __init__(self, config: ZillizDBConfig = None):
        """Initialize the database. Save the config and client as an attribute.

        :param config: Database configuration class instance.
        :type config: ZillizDBConfig
        """

        if config is None:
            self.config = ZillizDBConfig()
        else:
            self.config = config

        try:
            self.client = MilvusClient(
                uri=self.config.uri,
                token=self.config.token,
            )

            self.connection = connections.connect(
                uri=self.config.uri,
                token=self.config.token,
            )
        except Exception:
            raise ValueError("Credentials Provided are not Valid")

        super().__init__(config=self.config)

    def _initialize(self):
        """
        This method is needed because `embedder` attribute needs to be set externally before it can be initialized.

        So it's can't be done in __init__ in one step.
        """
        self._get_or_create_collection(self.config.collection_name)

    def _get_or_create_db(self):
        """Get or create the database."""
        return self.client

    def _get_or_create_collection(self, name):
        """
        Get or create a named collection.

        :param name: Name of the collection
        :type name: str
        """
        if utility.has_collection(name):
            self.collection = Collection(name)
        else:
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=512),
                FieldSchema(name="doc", dtype=DataType.VARCHAR, max_length=2048),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.embedder.vector_dimension),
            ]

            schema = CollectionSchema(fields, enable_dynamic_field=True)
            self.collection = Collection(name=name, schema=schema)

            index = {
                "index_type": "AUTOINDEX",
                "metric_type": "L2",
            }
            self.collection.create_index("vector", index)
        return self.collection

    def get(self, ids: Optional[List[str]] = None, where: Optional[Dict[str, any]] = None, limit: Optional[int] = None):
        """
        Get existing doc ids present in vector database

        :param ids: list of doc ids to check for existence
        :type ids: List[str]
        :param where: Optional. to filter data
        :type where: Dict[str, Any]
        :param limit: Optional. maximum number of documents
        :type limit: Optional[int]
        :return: Existing documents.
        :rtype: Set[str]
        """
        if ids is None or len(ids) == 0 or self.collection.num_entities == 0:
            return {"ids": []}

        if not (self.collection.is_empty):
            filter = f"id in {ids}"
            results = self.client.query(
                collection_name=self.config.collection_name, filter=filter, output_fields=["id"]
            )
            results = [res["id"] for res in results]

        return {"ids": set(results)}

    def add(
        self,
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[object],
        ids: List[str],
        skip_embedding: bool,
    ):
        """Add to database"""
        if not skip_embedding:
            embeddings = self.embedder.embedding_fn(documents)

        for id, doc, metadata, embedding in zip(ids, documents, metadatas, embeddings):
            data = {**metadata, "id": id, "doc": doc, "vector": embedding}
            self.client.insert(collection_name=self.config.collection_name, data=data)

        self.collection.load()
        self.collection.flush()
        self.client.flush(self.config.collection_name)

    def query(self, input_query: List[str], n_results: int, where: Dict[str, any], skip_embedding: bool) -> List[str]:
        """
        Query contents from vector data base based on vector similarity

        :param input_query: list of query string
        :type input_query: List[str]
        :param n_results: no of similar documents to fetch from database
        :type n_results: int
        :param where: to filter data
        :type where: str
        :raises InvalidDimensionException: Dimensions do not match.
        :return: The content of the document that matched your query.
        :rtype: List[str]
        """

        if not isinstance(where, str):
            where = None

        if skip_embedding:
            query_vector = input_query
            query_result = self.client.search(
                collection_name=self.config.collection_name,
                data=query_vector,
                limit=n_results,
                output_fields=["doc"],
            )

        else:
            input_query_vector = self.embedder.embedding_fn([input_query])
            query_vector = input_query_vector[0]

            query_result = self.client.search(
                collection_name=self.config.collection_name,
                data=[query_vector],
                limit=n_results,
                output_fields=["doc"],
            )

        doc_list = []
        for query in query_result:
            doc_list.append(query[0]["entity"]["doc"])

        return doc_list

    def count(self) -> int:
        """
        Count number of documents/chunks embedded in the database.

        :return: number of documents
        :rtype: int
        """
        return self.collection.num_entities

    def reset(self, collection_names: List[str] = None):
        """
        Resets the database. Deletes all embeddings irreversibly.
        """
        if self.config.collection_name:
            if collection_names:
                for collection_name in collection_names:
                    if collection_name in self.client.list_collections():
                        self.client.drop_collection(collection_name=collection_name)
            else:
                self.client.drop_collection(collection_name=self.config.collection_name)
                self._get_or_create_collection(self.config.collection_name)

    def set_collection_name(self, name: str):
        """
        Set the name of the collection. A collection is an isolated space for vectors.

        :param name: Name of the collection.
        :type name: str
        """
        if not isinstance(name, str):
            raise TypeError("Collection name must be a string")
        self.config.collection_name = name
