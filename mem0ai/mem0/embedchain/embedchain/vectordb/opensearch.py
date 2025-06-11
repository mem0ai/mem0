import logging
import time
from typing import Any, Optional, Union

from tqdm import tqdm

try:
    from opensearchpy import OpenSearch
    from opensearchpy.helpers import bulk
except ImportError:
    raise ImportError(
        "OpenSearch requires extra dependencies. Install with `pip install --upgrade embedchain[opensearch]`"
    ) from None

from langchain_community.embeddings.openai import OpenAIEmbeddings
from langchain_community.vectorstores import OpenSearchVectorSearch

from embedchain.config import OpenSearchDBConfig
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.vectordb.base import BaseVectorDB

logger = logging.getLogger(__name__)


@register_deserializable
class OpenSearchDB(BaseVectorDB):
    """
    OpenSearch as vector database
    """

    def __init__(self, config: OpenSearchDBConfig):
        """OpenSearch as vector database.

        :param config: OpenSearch domain config
        :type config: OpenSearchDBConfig
        """
        if config is None:
            raise ValueError("OpenSearchDBConfig is required")
        self.config = config
        self.batch_size = self.config.batch_size
        self.client = OpenSearch(
            hosts=[self.config.opensearch_url],
            http_auth=self.config.http_auth,
            **self.config.extra_params,
        )
        info = self.client.info()
        logger.info(f"Connected to {info['version']['distribution']}. Version: {info['version']['number']}")
        # Remove auth credentials from config after successful connection
        super().__init__(config=self.config)

    def _initialize(self):
        logger.info(self.client.info())
        index_name = self._get_index()
        if self.client.indices.exists(index=index_name):
            print(f"Index '{index_name}' already exists.")
            return

        index_body = {
            "settings": {"knn": True},
            "mappings": {
                "properties": {
                    "text": {"type": "text"},
                    "embeddings": {
                        "type": "knn_vector",
                        "index": False,
                        "dimension": self.config.vector_dimension,
                    },
                }
            },
        }
        self.client.indices.create(index_name, body=index_body)
        print(self.client.indices.get(index_name))

    def _get_or_create_db(self):
        """Called during initialization"""
        return self.client

    def _get_or_create_collection(self, name):
        """Note: nothing to return here. Discuss later"""

    def get(
        self, ids: Optional[list[str]] = None, where: Optional[dict[str, any]] = None, limit: Optional[int] = None
    ) -> set[str]:
        """
        Get existing doc ids present in vector database

        :param ids: _list of doc ids to check for existence
        :type ids: list[str]
        :param where: to filter data
        :type where: dict[str, any]
        :return: ids
        :type: set[str]
        """
        query = {}
        if ids:
            query["query"] = {"bool": {"must": [{"ids": {"values": ids}}]}}
        else:
            query["query"] = {"bool": {"must": []}}

        if where:
            for key, value in where.items():
                query["query"]["bool"]["must"].append({"term": {f"metadata.{key}.keyword": value}})

        # OpenSearch syntax is different from Elasticsearch
        response = self.client.search(index=self._get_index(), body=query, _source=True, size=limit)
        docs = response["hits"]["hits"]
        ids = [doc["_id"] for doc in docs]
        doc_ids = [doc["_source"]["metadata"]["doc_id"] for doc in docs]

        # Result is modified for compatibility with other vector databases
        # TODO: Add method in vector database to return result in a standard format
        result = {"ids": ids, "metadatas": []}

        for doc_id in doc_ids:
            result["metadatas"].append({"doc_id": doc_id})
        return result

    def add(self, documents: list[str], metadatas: list[object], ids: list[str], **kwargs: Optional[dict[str, any]]):
        """Adds documents to the opensearch index"""

        embeddings = self.embedder.embedding_fn(documents)
        for batch_start in tqdm(range(0, len(documents), self.batch_size), desc="Inserting batches in opensearch"):
            batch_end = batch_start + self.batch_size
            batch_documents = documents[batch_start:batch_end]
            batch_embeddings = embeddings[batch_start:batch_end]

            # Create document entries for bulk upload
            batch_entries = [
                {
                    "_index": self._get_index(),
                    "_id": doc_id,
                    "_source": {"text": text, "metadata": metadata, "embeddings": embedding},
                }
                for doc_id, text, metadata, embedding in zip(
                    ids[batch_start:batch_end], batch_documents, metadatas[batch_start:batch_end], batch_embeddings
                )
            ]

            # Perform bulk operation
            bulk(self.client, batch_entries, **kwargs)
            self.client.indices.refresh(index=self._get_index())

            # Sleep to avoid rate limiting
            time.sleep(0.1)

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
        :param citations: we use citations boolean param to return context along with the answer.
        :type citations: bool, default is False.
        :return: The content of the document that matched your query,
        along with url of the source and doc_id (if citations flag is true)
        :rtype: list[str], if citations=False, otherwise list[tuple[str, str, str]]
        """
        embeddings = OpenAIEmbeddings()
        docsearch = OpenSearchVectorSearch(
            index_name=self._get_index(),
            embedding_function=embeddings,
            opensearch_url=f"{self.config.opensearch_url}",
            http_auth=self.config.http_auth,
            use_ssl=hasattr(self.config, "use_ssl") and self.config.use_ssl,
            verify_certs=hasattr(self.config, "verify_certs") and self.config.verify_certs,
        )

        pre_filter = {"match_all": {}}  # default
        if len(where) > 0:
            pre_filter = {"bool": {"must": []}}
            for key, value in where.items():
                pre_filter["bool"]["must"].append({"term": {f"metadata.{key}.keyword": value}})

        docs = docsearch.similarity_search_with_score(
            input_query,
            search_type="script_scoring",
            space_type="cosinesimil",
            vector_field="embeddings",
            text_field="text",
            metadata_field="metadata",
            pre_filter=pre_filter,
            k=n_results,
            **kwargs,
        )

        contexts = []
        for doc, score in docs:
            context = doc.page_content
            if citations:
                metadata = doc.metadata
                metadata["score"] = score
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
        query = {"query": {"match_all": {}}}
        response = self.client.count(index=self._get_index(), body=query)
        doc_count = response["count"]
        return doc_count

    def reset(self):
        """
        Resets the database. Deletes all embeddings irreversibly.
        """
        # Delete all data from the database
        if self.client.indices.exists(index=self._get_index()):
            # delete index in ES
            self.client.indices.delete(index=self._get_index())

    def delete(self, where):
        """Deletes a document from the OpenSearch index"""
        query = {"query": {"bool": {"must": []}}}
        for key, value in where.items():
            query["query"]["bool"]["must"].append({"term": {f"metadata.{key}.keyword": value}})
        self.client.delete_by_query(index=self._get_index(), body=query)

    def _get_index(self) -> str:
        """Get the OpenSearch index for a collection

        :return: OpenSearch index
        :rtype: str
        """
        return self.config.collection_name
