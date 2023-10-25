import copy
from typing import Dict, List, Optional

try:
    import deeplake
    from deeplake.core.vectorstore import VectorStore
except ImportError:
    raise ImportError("Deeplake requires extra dependencies. Install with `pip install embedchain[deeplake]`") from None

from embedchain.config.vectordb.deeplake import DeeplakeDBConfig
from embedchain.vectordb.base import BaseVectorDB


class DeeplakeDB(BaseVectorDB):
    """
    Deeplake as vector database
    """

    BATCH_SIZE = 100
    DEFAULT_VECTORSTORE_TENSORS = [
        {
            "name": "text",
            "htype": "text",
        },
        {
            "name": "metadata",
            "htype": "json",
        },
        {
            "name": "embedding",
            "htype": "embedding",
            "dtype": float,
        },
        {
            "name": "id",
            "htype": "text",
        },
    ]

    def __init__(self, config: DeeplakeDBConfig = None):
        """
        Deeplake as vector database
        :param config. Deeplake database config to be used for connection
        """
        if config is None:
            config = DeeplakeDBConfig()
        else:
            if not isinstance(config, DeeplakeDBConfig):
                raise TypeError(
                    "config is not a `DeeplakeDBConfig` instance. "
                    "Please make sure the type is right and that you are passing an instance."
                )

        self.config = config
        if deeplake.exists(path=self.config.path):
            self.client = VectorStore(path=self.config.path, verbose=False)
        else:
            self.client = VectorStore(
                path=self.config.path, tensor_params=self.DEFAULT_VECTORSTORE_TENSORS, verbose=False
            )

        # Call parent init here because embedder is needed
        super().__init__(config=self.config)

    def _initialize(self):
        """
        This method is needed because `embedder` attribute needs to be set externally before it can be initialized.
        """
        if not self.embedder:
            raise ValueError("Embedder not set. Please set an embedder with `set_embedder` before initialization.")

        self.collection_name = self._get_or_create_collection()
        self.metadata_keys = {"data_type", "doc_id", "url", "hash", "app_id", "text"}

    def _get_or_create_db(self):
        return self.client

    def _get_or_create_collection(self):
        return f"{self.config.collection_name}-{self.embedder.vector_dimension}".lower().replace("_", "-")

    def get(self, ids: Optional[List[str]] = None, where: Optional[Dict[str, any]] = None, limit: Optional[int] = None):
        """
        Get existing doc ids present in vector database

        :param ids: _list of doc ids to check for existence
        :type ids: List[str]
        :param where: to filter data
        :type where: Dict[str, any]
        :param limit: The number of entries to be fetched
        :type limit: Optional int, defaults to None
        :return: All the existing IDs
        :rtype: Set[str]
        """
        if ids is None or len(ids) == 0 or self.client.__len__() == 0:
            return {"ids": []}

        keys = set(where.keys() if where is not None else set())

        deeplake_metadata_filter = {}
        if len(keys.intersection(self.metadata_keys)) != 0:
            for key in keys.intersection(self.metadata_keys):
                deeplake_metadata_filter[key] = where.get(key)

        results = self.client.search(
            exec_option=self.config.exec_option, filter={"metadata": deeplake_metadata_filter}, k=limit
        )

        identifiers = []
        for result in results.get("metadata", {}):
            identifiers.append(result.get("identifier"))
        return {"ids": identifiers}

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

        payloads = []
        for id, document, metadata in zip(ids, documents, metadatas):
            metadata["identifier"] = id
            payloads.append(copy.deepcopy(metadata))

        for i in range(0, len(metadatas), self.BATCH_SIZE):
            self.client.add(
                text=documents[i : i + self.BATCH_SIZE],
                embedding=embeddings[i : i + self.BATCH_SIZE],
                metadata=payloads[i : i + self.BATCH_SIZE],
            )

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
            query_vector = self.embedder.embedding_fn([input_query])[0]
        else:
            query_vector = input_query

        keys = set(where.keys() if where is not None else set())

        deeplake_metadata_filter = {}
        if len(keys.intersection(self.metadata_keys)) != 0:
            for key in keys.intersection(self.metadata_keys):
                deeplake_metadata_filter[key] = where.get(key)

        results = self.client.search(
            embedding=query_vector,
            exec_option=self.config.exec_option,
            filter={"metadata": deeplake_metadata_filter},
            k=n_results,
        )
        response = []
        for result in results.get("text", []):
            response.append(result)
        return response

    def count(self) -> int:
        return self.client.__len__()

    def reset(self):
        self.client.delete_by_path(self.config.path)
        self.client = VectorStore(path=self.config.path, tensor_params=self.DEFAULT_VECTORSTORE_TENSORS)
