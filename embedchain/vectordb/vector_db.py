from typing import Any, List, Optional, Union

from langchain.docstore.document import Document

from embedchain.vectordb.chroma_db import ChromaDB
from embedchain.vectordb.elasticsearch_db import EsDB


class VectorDb:
    """
    Database abstraction class, abstracting common functionality
        :param db: (Vector) database instance to use for embeddings. Can be es/chroma
        :param db_type: which type of database is used. [es, chroma]
    """

    def __init__(self, db: Union[ChromaDB, EsDB], db_type: Optional[str] = None):
        self.db = db
        self.db_type = db_type

    """
        Get existing doc ids present in vector database
        :param ids: list of doc ids to check for existance
        :param app_id: Optional application to filter data 
    """

    def get(self, ids: List[str], app_id: Optional[str]) -> List[str]:
        if self.db_type == "es":
            query = {"bool": {"must": [{"ids": {"values": ids}}]}}
            if app_id:
                query["bool"]["must"].append({"term": {"metadata.app_id": app_id}})
            response = self.db.client.search(index=self.db.es_index, query=query, _source=False)
            docs = response["hits"]["hits"]
            ids = [doc["_id"] for doc in docs]
            return set(ids)

        where = {"app_id": app_id} if app_id is not None else {}
        existing_docs = self.db.collection.get(
            ids=ids,
            where=where,  # optional filter
        )

        return set(existing_docs["ids"])

    """
    add data in vector database
    :param documents: list of texts to add
    :param metadatas: list of metadata associated with docs
    :param ids: ids of docs 
    """

    def add(self, documents: List[str], metadatas: List[object], ids: List[str]) -> Any:
        if self.db_type == "es":
            docs = []
            embeddings = self.db.embedding_fn(documents)
            for id, text, metadata, text_vector in zip(ids, documents, metadatas, embeddings):
                docs.append(
                    {
                        "_index": self.db.es_index,
                        "_id": id,
                        "_source": {"text": text, "metadata": metadata, "text_vector": text_vector},
                    }
                )
            self.db.bulk(self.db.client, docs)
            self.db.client.indices.refresh(index=self.db.es_index)
            return

        self.db.collection.add(documents=documents, metadatas=metadatas, ids=ids)

    def _format_result(self, results):
        # discuss why there was a need to create lagchain Document
        return [
            (Document(page_content=result[0], metadata=result[1] or {}), result[2])
            for result in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]

    """
        query contents from vector data base based on vector similarity
        :param input_query: list of query string
        :param number_documents: no of similar documents to fetch from database
        :param app_id: Optional app id for filtering data 
    """

    def query(
        self, input_query: List[str], number_documents: int, app_id: Optional[Union[int, str]] = None
    ) -> List[str]:
        if self.db_type == "es":
            """
            Currently have taken max 2048 as vector dim, there is a need to re check the
            accuracy of cosineSimilarity used to retrive similar documents
            Not using Approximate kNN because cannot index dense vector due to dims > 1024
            https://www.elastic.co/guide/en/elasticsearch/reference/master/knn-search.html
            Using Exact KNN
            https://www.elastic.co/guide/en/elasticsearch/reference/master/knn-search.html#exact-knn
            """
            input_query_vector = self.db.embedding_fn(input_query)
            query_vector = input_query_vector[0]
            query = {
                "script_score": {
                    "query": {"bool": {"must": [{"exists": {"field": "text"}}]}},
                    "script": {
                        "source": "cosineSimilarity(params.input_query_vector, 'text_vector') + 1.0",
                        "params": {"input_query_vector": query_vector},
                    },
                }
            }
            if app_id:
                query["script_score"]["query"]["bool"]["must"] = [{"term": {"metadata.app_id": app_id}}]
            _source = ["text"]
            size = number_documents
            response = self.db.client.search(index=self.db.es_index, query=query, _source=_source, size=size)
            docs = response["hits"]["hits"]
            contents = [doc["_source"]["text"] for doc in docs]
            return contents

        where = {"app_id": app_id} if app_id is not None else {}  # optional filter
        result = self.db.collection.query(
            query_texts=[
                input_query,
            ],
            n_results=number_documents,
            where=where,
        )

        results_formatted = self._format_result(result)
        contents = [result[0].page_content for result in results_formatted]
        return contents

    """
    get count of docs in the database
    :param app_id: Optional app id to filter data
    """

    def count(self, app_id: Optional[Union[int, str]] = None) -> int:
        if self.db_type == "es":
            query = {"match_all": {}}
            if app_id:
                query = {"bool": {"must": [{"term": {"metadata.app_id": app_id}}]}}
            response = self.db.client.count(index=self.db.es_index, query=query)
            doc_count = response["count"]
            return doc_count

        return self.db.collection.count()

    # Delete all data from the database
    def reset(self):
        if self.db_type == "es" and self.db.client.indices.exists(index=self.db.es_index):
            # delete index in Es
            self.db.client.indices.delete(index=self.db.es_index)
            return

        self.db.collection.delete()

    # get Vector Db instance
    def get_db(self):
        return self.db
