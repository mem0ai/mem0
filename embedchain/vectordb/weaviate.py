import copy
import os
from typing import Dict, List, Optional

try:
    import weaviate
except ImportError:
    raise ImportError(
        "Weaviate requires extra dependencies. Install with `pip install --upgrade embedchain[weaviate]`"
    ) from None

from embedchain.config.vectordb.weaviate import WeaviateDbConfig
from embedchain.helper.json_serializable import register_deserializable
from embedchain.vectordb.base import BaseVectorDB


@register_deserializable
class WeaviateDb(BaseVectorDB):
    """
    Weaviate as vector database
    """

    def __init__(
        self,
        config: Optional[WeaviateDbConfig] = None,
    ):
        """Weaviate as vector database.
        :param config: Weaviate database config, defaults to None
        :type config: WeaviateDbConfig, optional
        :raises ValueError: No config provided
        """
        if config is None:
            self.config = WeaviateDbConfig()
        else:
            if not isinstance(config, WeaviateDbConfig):
                raise TypeError(
                    "config is not a `WeaviateDbConfig` instance. "
                    "Please make sure the type is right and that you are passing an instance."
                )
            self.config = config
        self.client = weaviate.Client(
            url=os.environ.get("WEAVIATE_ENDPOINT"),
            auth_client_secret=weaviate.AuthApiKey(api_key=os.environ.get("WEAVIATE_API_KEY")),
            additional_headers={"X-OpenAI-Api-Key": os.environ.get("OPENAI_API_KEY")},
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
        if not self.client.schema.exists(self.index_name):
            # id is a reserved field in Weaviate, hence we had to change the name of the id field to identifier
            class_obj = {
                "classes": [
                    {
                        "class": self.index_name,
                        "properties": [
                            {
                                "name": "identifier",
                                "dataType": ["text"],
                            },
                            {
                                "name": "text",
                                "dataType": ["text"],
                            },
                        ],
                    }
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

        results = (
            self.client.query.get(self.index_name, ["identifier"])
            .with_where({
                "path": ["identifier"],
                "operator": "ContainsAny",
                "valueText": ids
            }).do()
        )

        existing_ids = []
        for result in results["data"]["Get"].get(self.index_name, []):
            existing_ids.append(result["identifier"])
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

        if not skip_embedding:
            embeddings = self.embedder.embedding_fn(documents)
        self.client.batch.configure(batch_size=100, timeout_retries=3)  # Configure batch
        new_documents = []
        with self.client.batch as batch:  # Initialize a batch process
            for id, text, embedding in zip(ids, documents, embeddings):
                doc = {"identifier": id, "text": text}
                new_documents.append(copy.deepcopy(doc))
                batch.add_data_object(data_object=copy.deepcopy(doc), class_name=self.index_name, vector=embedding)

    def query(self, input_query: List[str], n_results: int, where: Dict[str, any], skip_embedding: bool) -> List[str]:
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
        :return: Database contents that are the result of the query
        :rtype: List[str]
        """
        if not skip_embedding:
            query_vector = self.embedder.embedding_fn(input_query)[0]
        else:
            query_vector = input_query

        keys = list(where.keys() if where is not None else [])
        values = list(where.values() if where is not None else [])
        if where is not None and ("id" in keys or "text" in keys):
            default_filter_params = {"path": keys, "operator": "Equal", "valueTextArray": values}
            default_filter_params.update(where)

            if default_filter_params.keys().__contains__("id"):
                default_filter_params["identifier"] = default_filter_params.get("id", None)

            results = (
                self.client.query.get(self.index_name, ["identifier", "text"])
                .with_where(default_filter_params)
                .with_near_vector({"vector": query_vector})
                .with_limit(n_results)
                .do()
            )

        else:
            results = (
                self.client.query.get(self.index_name, ["text"])
                .with_near_vector({"vector": query_vector})
                .with_limit(n_results)
                .do()
            )
        matched_tokens = []
        for result in results["data"]["Get"].get(self.index_name):
            matched_tokens.append(result["text"])
        return matched_tokens

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
