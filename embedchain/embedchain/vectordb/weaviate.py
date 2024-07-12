import copy
import os
from typing import Optional, Union

try:
    import weaviate
except ImportError:
    raise ImportError(
        "Weaviate requires extra dependencies. Install with `pip install --upgrade 'embedchain[weaviate]'`"
    ) from None

from embedchain.config.vector_db.weaviate import WeaviateDBConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.vectordb.base import BaseVectorDB


@register_deserializable
class WeaviateDB(BaseVectorDB):
    """
    Weaviate as vector database
    """

    def __init__(
        self,
        config: Optional[WeaviateDBConfig] = None,
    ):
        """Weaviate as vector database.
        :param config: Weaviate database config, defaults to None
        :type config: WeaviateDBConfig, optional
        :raises ValueError: No config provided
        """
        if config is None:
            self.config = WeaviateDBConfig()
        else:
            if not isinstance(config, WeaviateDBConfig):
                raise TypeError(
                    "config is not a `WeaviateDBConfig` instance. "
                    "Please make sure the type is right and that you are passing an instance."
                )
            self.config = config
        self.batch_size = self.config.batch_size
        self.client = weaviate.Client(
            url=os.environ.get("WEAVIATE_ENDPOINT"),
            auth_client_secret=weaviate.AuthApiKey(api_key=os.environ.get("WEAVIATE_API_KEY")),
            **self.config.extra_params,
        )
        # Since weaviate uses graphQL, we need to keep track of metadata keys added in the vectordb.
        # This is needed to filter data while querying.
        self.metadata_keys = {"data_type", "doc_id", "url", "hash", "app_id"}

        # Call parent init here because embedder is needed
        super().__init__(config=self.config)

    def _initialize(self):
        """
        This method is needed because `embedder` attribute needs to be set externally before it can be initialized.
        """

        if not self.embedder:
            raise ValueError("Embedder not set. Please set an embedder with `set_embedder` before initialization.")

        self.index_name = self._get_index_name()
        if not self.client.schema.exists(self.index_name):
            # id is a reserved field in Weaviate, hence we had to change the name of the id field to identifier
            # The none vectorizer is crucial as we have our own custom embedding function
            """
            TODO: wait for weaviate to add indexing on `object[]` data-type so that we can add filter while querying.
            Once that is done, change `dataType` of "metadata" field to `object[]` and update the query below.
            """
            class_obj = {
                "classes": [
                    {
                        "class": self.index_name,
                        "vectorizer": "none",
                        "properties": [
                            {
                                "name": "identifier",
                                "dataType": ["text"],
                            },
                            {
                                "name": "text",
                                "dataType": ["text"],
                            },
                            {
                                "name": "metadata",
                                "dataType": [self.index_name + "_metadata"],
                            },
                        ],
                    },
                    {
                        "class": self.index_name + "_metadata",
                        "vectorizer": "none",
                        "properties": [
                            {
                                "name": "data_type",
                                "dataType": ["text"],
                            },
                            {
                                "name": "doc_id",
                                "dataType": ["text"],
                            },
                            {
                                "name": "url",
                                "dataType": ["text"],
                            },
                            {
                                "name": "hash",
                                "dataType": ["text"],
                            },
                            {
                                "name": "app_id",
                                "dataType": ["text"],
                            },
                        ],
                    },
                ]
            }

            self.client.schema.create(class_obj)

    def get(self, ids: Optional[list[str]] = None, where: Optional[dict[str, any]] = None, limit: Optional[int] = None):
        """
        Get existing doc ids present in vector database
        :param ids: _list of doc ids to check for existance
        :type ids: list[str]
        :param where: to filter data
        :type where: dict[str, any]
        :return: ids
        :rtype: Set[str]
        """
        weaviate_where_operands = []

        if ids:
            for doc_id in ids:
                weaviate_where_operands.append({"path": ["identifier"], "operator": "Equal", "valueText": doc_id})

        keys = set(where.keys() if where is not None else set())
        if len(keys) > 0:
            for key in keys:
                weaviate_where_operands.append(
                    {
                        "path": ["metadata", self.index_name + "_metadata", key],
                        "operator": "Equal",
                        "valueText": where.get(key),
                    }
                )

        if len(weaviate_where_operands) == 1:
            weaviate_where_clause = weaviate_where_operands[0]
        else:
            weaviate_where_clause = {"operator": "And", "operands": weaviate_where_operands}

        existing_ids = []
        metadatas = []
        cursor = None
        offset = 0
        has_iterated_once = False
        query_metadata_keys = self.metadata_keys.union(keys)
        while cursor is not None or not has_iterated_once:
            has_iterated_once = True
            results = self._query_with_offset(
                self.client.query.get(
                    self.index_name,
                    [
                        "identifier",
                        weaviate.LinkTo("metadata", self.index_name + "_metadata", list(query_metadata_keys)),
                    ],
                )
                .with_where(weaviate_where_clause)
                .with_additional(["id"])
                .with_limit(limit or self.batch_size),
                offset,
            )

            fetched_results = results["data"]["Get"].get(self.index_name, [])
            if not fetched_results:
                break

            for result in fetched_results:
                existing_ids.append(result["identifier"])
                metadatas.append(result["metadata"][0])
                cursor = result["_additional"]["id"]
                offset += 1

            if limit is not None and len(existing_ids) >= limit:
                break

        return {"ids": existing_ids, "metadatas": metadatas}

    def add(self, documents: list[str], metadatas: list[object], ids: list[str], **kwargs: Optional[dict[str, any]]):
        """add data in vector database
        :param documents: list of texts to add
        :type documents: list[str]
        :param metadatas: list of metadata associated with docs
        :type metadatas: list[object]
        :param ids: ids of docs
        :type ids: list[str]
        """
        embeddings = self.embedder.embedding_fn(documents)
        self.client.batch.configure(batch_size=self.batch_size, timeout_retries=3)  # Configure batch
        with self.client.batch as batch:  # Initialize a batch process
            for id, text, metadata, embedding in zip(ids, documents, metadatas, embeddings):
                doc = {"identifier": id, "text": text}
                updated_metadata = {"text": text}
                if metadata is not None:
                    updated_metadata.update(**metadata)

                obj_uuid = batch.add_data_object(
                    data_object=copy.deepcopy(doc), class_name=self.index_name, vector=embedding
                )
                metadata_uuid = batch.add_data_object(
                    data_object=copy.deepcopy(updated_metadata),
                    class_name=self.index_name + "_metadata",
                    vector=embedding,
                )
                batch.add_reference(
                    obj_uuid, self.index_name, "metadata", metadata_uuid, self.index_name + "_metadata", **kwargs
                )

    def query(
        self, input_query: str, n_results: int, where: dict[str, any], citations: bool = False
    ) -> Union[list[tuple[str, dict]], list[str]]:
        """
        query contents from vector database based on vector similarity
        :param input_query: query string
        :type input_query: str
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
        query_vector = self.embedder.embedding_fn([input_query])[0]
        keys = set(where.keys() if where is not None else set())
        data_fields = ["text"]
        query_metadata_keys = self.metadata_keys.union(keys)
        if citations:
            data_fields.append(weaviate.LinkTo("metadata", self.index_name + "_metadata", list(query_metadata_keys)))

        if len(keys) > 0:
            weaviate_where_operands = []
            for key in keys:
                weaviate_where_operands.append(
                    {
                        "path": ["metadata", self.index_name + "_metadata", key],
                        "operator": "Equal",
                        "valueText": where.get(key),
                    }
                )
            if len(weaviate_where_operands) == 1:
                weaviate_where_clause = weaviate_where_operands[0]
            else:
                weaviate_where_clause = {"operator": "And", "operands": weaviate_where_operands}

            results = (
                self.client.query.get(self.index_name, data_fields)
                .with_where(weaviate_where_clause)
                .with_near_vector({"vector": query_vector})
                .with_limit(n_results)
                .with_additional(["distance"])
                .do()
            )
        else:
            results = (
                self.client.query.get(self.index_name, data_fields)
                .with_near_vector({"vector": query_vector})
                .with_limit(n_results)
                .with_additional(["distance"])
                .do()
            )

        if results["data"]["Get"].get(self.index_name) is None:
            return []

        docs = results["data"]["Get"].get(self.index_name)
        contexts = []
        for doc in docs:
            context = doc["text"]
            if citations:
                metadata = doc["metadata"][0]
                score = doc["_additional"]["distance"]
                metadata["score"] = score
                contexts.append((context, metadata))
            else:
                contexts.append(context)
        return contexts

    def set_collection_name(self, name: str):
        """
        Set the name of the collection. A collection is an isolated space for vectors.
        :param name: Name of the collection.
        :type name: str
        """
        if not isinstance(name, str):
            raise TypeError("Collection name must be a string")
        self.config.collection_name = name

    def count(self) -> int:
        """
        Count number of documents/chunks embedded in the database.
        :return: number of documents
        :rtype: int
        """
        data = self.client.query.aggregate(self.index_name).with_meta_count().do()
        return data["data"]["Aggregate"].get(self.index_name)[0]["meta"]["count"]

    def _get_or_create_db(self):
        """Called during initialization"""
        return self.client

    def reset(self):
        """
        Resets the database. Deletes all embeddings irreversibly.
        """
        # Delete all data from the database
        self.client.batch.delete_objects(
            self.index_name, where={"path": ["identifier"], "operator": "Like", "valueText": ".*"}
        )

    # Weaviate internally by default capitalizes the class name
    def _get_index_name(self) -> str:
        """Get the Weaviate index for a collection
        :return: Weaviate index
        :rtype: str
        """
        return f"{self.config.collection_name}_{self.embedder.vector_dimension}".capitalize().replace("-", "_")

    @staticmethod
    def _query_with_offset(query, offset):
        if offset:
            query.with_offset(offset)
        results = query.do()
        return results

    def _generate_query(self, where: dict):
        weaviate_where_operands = []
        for key, value in where.items():
            weaviate_where_operands.append(
                {
                    "path": ["metadata", self.index_name + "_metadata", key],
                    "operator": "Equal",
                    "valueText": value,
                }
            )

        if len(weaviate_where_operands) == 1:
            weaviate_where_clause = weaviate_where_operands[0]
        else:
            weaviate_where_clause = {"operator": "And", "operands": weaviate_where_operands}

        return weaviate_where_clause

    def delete(self, where: dict):
        """Delete from database.
        :param where: to filter data
        :type where: dict[str, any]
        """
        query = self._generate_query(where)
        self.client.batch.delete_objects(self.index_name, where=query)
