import copy
import os
from typing import Dict, List, Optional, Tuple

try:
    import weaviate
except ImportError:
    raise ImportError(
        "Weaviate requires extra dependencies. Install with `pip install --upgrade 'embedchain[weaviate]'`"
    ) from None

from embedchain.config.vectordb.weaviate import WeaviateDBConfig
from embedchain.helper.json_serializable import register_deserializable
from embedchain.vectordb.base import BaseVectorDB


@register_deserializable
class WeaviateDB(BaseVectorDB):
    """
    Weaviate as vector database
    """

    BATCH_SIZE = 100

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
        self.client = weaviate.Client(
            url=os.environ.get("WEAVIATE_ENDPOINT"),
            auth_client_secret=weaviate.AuthApiKey(api_key=os.environ.get("WEAVIATE_API_KEY")),
            **self.config.extra_params,
        )

        # Call parent init here because embedder is needed
        super().__init__(config=self.config)

    def _initialize(self):
        """
        This method is needed because `embedder` attribute needs to be set externally before it can be initialized.
        """

        if not self.embedder:
            raise ValueError("Embedder not set. Please set an embedder with `set_embedder` before initialization.")

        self.index_name = self._get_index_name()
        self.metadata_keys = {"data_type", "doc_id", "url", "hash", "app_id", "text"}
        if not self.client.schema.exists(self.index_name):
            # id is a reserved field in Weaviate, hence we had to change the name of the id field to identifier
            # The none vectorizer is crucial as we have our own custom embedding function
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
                            {
                                "name": "text",
                                "dataType": ["text"],
                            },
                        ],
                    },
                ]
            }

            self.client.schema.create(class_obj)

    def get(self, ids: Optional[List[str]] = None, where: Optional[Dict[str, any]] = None, limit: Optional[int] = None):
        """
        Get existing doc ids present in vector database
        :param ids: _list of doc ids to check for existance
        :type ids: List[str]
        :param where: to filter data
        :type where: Dict[str, any]
        :return: ids
        :rtype: Set[str]
        """

        if ids is None or len(ids) == 0:
            return {"ids": []}

        existing_ids = []
        cursor = None
        has_iterated_once = False
        while cursor is not None or not has_iterated_once:
            has_iterated_once = True
            results = self._query_with_cursor(
                self.client.query.get(self.index_name, ["identifier"])
                .with_additional(["id"])
                .with_limit(self.BATCH_SIZE),
                cursor,
            )
            fetched_results = results["data"]["Get"].get(self.index_name, [])
            if len(fetched_results) == 0:
                break
            for result in fetched_results:
                existing_ids.append(result["identifier"])
                cursor = result["_additional"]["id"]

        return {"ids": existing_ids}

    def add(
        self,
        embeddings: List[List[float]],
        documents: List[str],
        metadatas: List[object],
        ids: List[str],
        skip_embedding: bool,
    ):
        """add data in vector database
        :param embeddings: list of embeddings for the corresponding documents to be added
        :type documents: List[List[float]]
        :param documents: list of texts to add
        :type documents: List[str]
        :param metadatas: list of metadata associated with docs
        :type metadatas: List[object]
        :param ids: ids of docs
        :type ids: List[str]
        :param skip_embedding: A boolean flag indicating if the embedding for the documents to be added is to be
        generated or not
        :type skip_embedding: bool
        """

        print("Adding documents to Weaviate...")
        if not skip_embedding:
            embeddings = self.embedder.embedding_fn(documents)
        self.client.batch.configure(batch_size=self.BATCH_SIZE, timeout_retries=3)  # Configure batch
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
                batch.add_reference(obj_uuid, self.index_name, "metadata", metadata_uuid, self.index_name + "_metadata")

    def query(
        self, input_query: List[str], n_results: int, where: Dict[str, any], skip_embedding: bool
    ) -> List[Tuple[str, str, str]]:
        """
        query contents from vector database based on vector similarity
        :param input_query: list of query string
        :type input_query: List[str]
        :param n_results: no of similar documents to fetch from database
        :type n_results: int
        :param where: Optional. to filter data
        :type where: Dict[str, any]
        :param skip_embedding: A boolean flag indicating if the embedding for the documents to be added is to be
        generated or not
        :type skip_embedding: bool
        :return: The context of the document that matched your query, url of the source, doc_id
        :rtype: List[Tuple[str,str,str]]
        """
        if not skip_embedding:
            query_vector = self.embedder.embedding_fn([input_query])[0]
        else:
            query_vector = input_query
        keys = set(where.keys() if where is not None else set())
        data_fields = ["text"]
        if len(keys.intersection(self.metadata_keys)) != 0:
            weaviate_where_operands = []
            for key in keys:
                if key in self.metadata_keys:
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
                .do()
            )
        else:
            results = (
                self.client.query.get(self.index_name, data_fields)
                .with_near_vector({"vector": query_vector})
                .with_limit(n_results)
                .do()
            )
        contexts = results["data"]["Get"].get(self.index_name)
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
        return f"{self.config.collection_name}_{self.embedder.vector_dimension}".capitalize()

    def _query_with_cursor(self, query, cursor):
        if cursor is not None:
            query.with_after(cursor)
        results = query.do()
        return results
