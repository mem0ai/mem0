import logging
from typing import Any, Optional, Union

try:
    from elasticsearch import Elasticsearch
    from elasticsearch.helpers import bulk
except ImportError:
    raise ImportError(
        "Elasticsearch requires extra dependencies. Install with `pip install --upgrade embedchain[elasticsearch]`"
    ) from None

from embedchain.config import ElasticsearchDBConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.utils.misc import chunks
from embedchain.vectordb.base import BaseVectorDB

logger = logging.getLogger(__name__)


@register_deserializable
class ElasticsearchDB(BaseVectorDB):
    """
    Elasticsearch as vector database
    """

    def __init__(
        self,
        config: Optional[ElasticsearchDBConfig] = None,
        es_config: Optional[ElasticsearchDBConfig] = None,  # Backwards compatibility
    ):
        """Elasticsearch as vector database.

        :param config: Elasticsearch database config, defaults to None
        :type config: ElasticsearchDBConfig, optional
        :param es_config: `es_config` is supported as an alias for `config` (for backwards compatibility),
        defaults to None
        :type es_config: ElasticsearchDBConfig, optional
        :raises ValueError: No config provided
        """
        if config is None and es_config is None:
            self.config = ElasticsearchDBConfig()
        else:
            if not isinstance(config, ElasticsearchDBConfig):
                raise TypeError(
                    "config is not a `ElasticsearchDBConfig` instance. "
                    "Please make sure the type is right and that you are passing an instance."
                )
            self.config = config or es_config
        if self.config.ES_URL:
            self.client = Elasticsearch(self.config.ES_URL, **self.config.ES_EXTRA_PARAMS)
        elif self.config.CLOUD_ID:
            self.client = Elasticsearch(cloud_id=self.config.CLOUD_ID, **self.config.ES_EXTRA_PARAMS)
        else:
            raise ValueError(
                "Something is wrong with your config. Please check again - `https://docs.embedchain.ai/components/vector-databases#elasticsearch`"  # noqa: E501
            )

        self.batch_size = self.config.batch_size
        # Call parent init here because embedder is needed
        super().__init__(config=self.config)

    def _initialize(self):
        """
        This method is needed because `embedder` attribute needs to be set externally before it can be initialized.
        """
        logger.info(self.client.info())
        index_settings = {
            "mappings": {
                "properties": {
                    "text": {"type": "text"},
                    "embeddings": {"type": "dense_vector", "index": False, "dims": self.embedder.vector_dimension},
                }
            }
        }
        es_index = self._get_index()
        if not self.client.indices.exists(index=es_index):
            # create index if not exist
            print("Creating index", es_index, index_settings)
            self.client.indices.create(index=es_index, body=index_settings)

    def _get_or_create_db(self):
        """Called during initialization"""
        return self.client

    def _get_or_create_collection(self, name):
        """Note: nothing to return here. Discuss later"""

    def get(self, ids: Optional[list[str]] = None, where: Optional[dict[str, any]] = None, limit: Optional[int] = None):
        """
        Get existing doc ids present in vector database

        :param ids: _list of doc ids to check for existence
        :type ids: list[str]
        :param where: to filter data
        :type where: dict[str, any]
        :return: ids
        :rtype: Set[str]
        """
        if ids:
            query = {"bool": {"must": [{"ids": {"values": ids}}]}}
        else:
            query = {"bool": {"must": []}}

        if where:
            for key, value in where.items():
                query["bool"]["must"].append({"term": {f"metadata.{key}.keyword": value}})

        response = self.client.search(index=self._get_index(), query=query, _source=True, size=limit)
        docs = response["hits"]["hits"]
        ids = [doc["_id"] for doc in docs]
        doc_ids = [doc["_source"]["metadata"]["doc_id"] for doc in docs]

        # Result is modified for compatibility with other vector databases
        # TODO: Add method in vector database to return result in a standard format
        result = {"ids": ids, "metadatas": []}

        for doc_id in doc_ids:
            result["metadatas"].append({"doc_id": doc_id})

        return result

    def add(
        self,
        documents: list[str],
        metadatas: list[object],
        ids: list[str],
        **kwargs: Optional[dict[str, any]],
    ) -> Any:
        """
        add data in vector database
        :param documents: list of texts to add
        :type documents: list[str]
        :param metadatas: list of metadata associated with docs
        :type metadatas: list[object]
        :param ids: ids of docs
        :type ids: list[str]
        """

        embeddings = self.embedder.embedding_fn(documents)

        for chunk in chunks(
            list(zip(ids, documents, metadatas, embeddings)),
            self.batch_size,
            desc="Inserting batches in elasticsearch",
        ):  # noqa: E501
            ids, docs, metadatas, embeddings = [], [], [], []
            for id, text, metadata, embedding in chunk:
                ids.append(id)
                docs.append(text)
                metadatas.append(metadata)
                embeddings.append(embedding)

            batch_docs = []
            for id, text, metadata, embedding in zip(ids, docs, metadatas, embeddings):
                batch_docs.append(
                    {
                        "_index": self._get_index(),
                        "_id": id,
                        "_source": {"text": text, "metadata": metadata, "embeddings": embedding},
                    }
                )
            bulk(self.client, batch_docs, **kwargs)
        self.client.indices.refresh(index=self._get_index())

    def query(
        self,
        input_query: str,
        n_results: int,
        where: dict[str, any],
        citations: bool = False,
        **kwargs: Optional[dict[str, Any]],
    ) -> Union[list[tuple[str, dict]], list[str]]:
        """
        query contents from vector database based on vector similarity

        :param input_query: query string
        :type input_query: str
        :param n_results: no of similar documents to fetch from database
        :type n_results: int
        :param where: Optional. to filter data
        :type where: dict[str, any]
        :return: The context of the document that matched your query, url of the source, doc_id
        :param citations: we use citations boolean param to return context along with the answer.
        :type citations: bool, default is False.
        :return: The content of the document that matched your query,
        along with url of the source and doc_id (if citations flag is true)
        :rtype: list[str], if citations=False, otherwise list[tuple[str, str, str]]
        """
        input_query_vector = self.embedder.embedding_fn([input_query])
        query_vector = input_query_vector[0]

        # `https://www.elastic.co/guide/en/elasticsearch/reference/7.17/query-dsl-script-score-query.html`
        query = {
            "script_score": {
                "query": {"bool": {"must": [{"exists": {"field": "text"}}]}},
                "script": {
                    "source": "cosineSimilarity(params.input_query_vector, 'embeddings') + 1.0",
                    "params": {"input_query_vector": query_vector},
                },
            }
        }

        if where:
            for key, value in where.items():
                query["script_score"]["query"]["bool"]["must"].append({"term": {f"metadata.{key}.keyword": value}})

        _source = ["text", "metadata"]
        response = self.client.search(index=self._get_index(), query=query, _source=_source, size=n_results)
        docs = response["hits"]["hits"]
        contexts = []
        for doc in docs:
            context = doc["_source"]["text"]
            if citations:
                metadata = doc["_source"]["metadata"]
                metadata["score"] = doc["_score"]
                contexts.append(tuple((context, metadata)))
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
        query = {"match_all": {}}
        response = self.client.count(index=self._get_index(), query=query)
        doc_count = response["count"]
        return doc_count

    def reset(self):
        """
        Resets the database. Deletes all embeddings irreversibly.
        """
        # Delete all data from the database
        if self.client.indices.exists(index=self._get_index()):
            # delete index in Es
            self.client.indices.delete(index=self._get_index())

    def _get_index(self) -> str:
        """Get the Elasticsearch index for a collection

        :return: Elasticsearch index
        :rtype: str
        """
        # NOTE: The method is preferred to an attribute, because if collection name changes,
        # it's always up-to-date.
        return f"{self.config.collection_name}_{self.embedder.vector_dimension}".lower()

    def delete(self, where):
        """Delete documents from the database."""
        query = {"query": {"bool": {"must": []}}}
        for key, value in where.items():
            query["query"]["bool"]["must"].append({"term": {f"metadata.{key}.keyword": value}})
        self.client.delete_by_query(index=self._get_index(), body=query)
        self.client.indices.refresh(index=self._get_index())
