import logging
from typing import Optional

from pydantic import BaseModel

try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    raise ImportError("Chromadb requires extra dependencies. Install with `pip install chromadb`") from None

from mem0.vector_stores.base import VectorStoreBase


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # distance 
    payload: Optional[dict]  # metadata


class ChromaDB(VectorStoreBase):
    def __init__(
        self,
        collection_name="mem0",
        client=None,
        host=None,
        port=None,
        path=None
    ):
        """
        Initialize the Qdrant vector store.

        Args:
            client (QdrantClient, optional): Existing Qdrant client instance. Defaults to None.
            host (str, optional): Host address for Qdrant server. Defaults to None.
            port (int, optional): Port for Qdrant server. Defaults to None.
            path (str, optional): Path for local Qdrant database. Defaults to None.
        """
        if client:
            self.client = client
        else:
            self.settings = Settings(anonymized_telemetry=False)

            if host and port:
                self.settings.chroma_server_host = host
                self.settings.chroma_server_http_port = port
                self.settings.chroma_api_impl = "chromadb.api.fastapi.FastAPI"
            else:
                if path is None:
                    path = "db"

            self.settings.persist_directory = path
            self.settings.is_persistent = True

            self.client = chromadb.Client(self.settings)

        self.collection = self.create_col(collection_name)

    def _parse_output(self, data):
        """
        Parse the output data.

        Args:
            data (dict): Output data.

        Returns:
            list: Parsed output data.
        """
        keys = ['ids', 'distances', 'metadatas']
        values = []

        for key in keys:
            value = data.get(key, [])
            if isinstance(value, list) and value and isinstance(value[0], list):
                value = value[0]
            values.append(value)

        ids, distances, metadatas = values
        max_length = max(len(v) for v in values if isinstance(v, list) and v is not None)

        result = []
        for i in range(max_length):
            entry = OutputData(
            id=ids[i] if isinstance(ids, list) and ids and i < len(ids) else None,
            score=distances[i] if isinstance(distances, list) and distances and i < len(distances) else None,
            payload=metadatas[i] if isinstance(metadatas, list) and metadatas and i < len(metadatas) else None,
        )
            result.append(entry)

        return result

    def create_col(self, name, embedding_fn=None):
        """
        Create a new collection.

        Args:
            name (str): Name of the collection.
            embedding_fn (function): Embedding function to use.
        """
        # Skip creating collection if already exists
        collections = self.list_cols()
        for collection in collections:
            if collection.name == name:
                logging.debug(f"Collection {name} already exists. Skipping creation.")

        collection = self.client.get_or_create_collection(
            name=name,
            embedding_function=embedding_fn,
        )
        return collection

    def insert(self, name, vectors, payloads=None, ids=None):
        """
        Insert vectors into a collection.

        Args:
            name (str): Name of the collection.
            vectors (list): List of vectors to insert.
            payloads (list, optional): List of payloads corresponding to vectors. Defaults to None.
            ids (list, optional): List of IDs corresponding to vectors. Defaults to None.
        """

        self.collection.add(ids=ids, embeddings=vectors, metadatas=payloads)

    def search(self, name, query, limit=5, filters=None):
        """
        Search for similar vectors.

        Args:
            name (str): Name of the collection.
            query (list): Query vector.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """
        results = self.collection.query(query_embeddings=query, where=filters, n_results=limit)
        final_results = self._parse_output(results)
        return final_results

    def delete(self, name, vector_id):
        """
        Delete a vector by ID.

        Args:
            name (str): Name of the collection.
            vector_id (int): ID of the vector to delete.
        """

        self.collection.delete(ids=vector_id)

    def update(self, name, vector_id, vector=None, payload=None):
        """
        Update a vector and its payload.

        Args:
            name (str): Name of the collection.
            vector_id (int): ID of the vector to update.
            vector (list, optional): Updated vector. Defaults to None.
            payload (dict, optional): Updated payload. Defaults to None.
        """

        self.collection.update(ids=vector_id, embeddings=vector, metadatas=payload)

    def get(self, name, vector_id):
        """
        Retrieve a vector by ID.

        Args:
            name (str): Name of the collection.
            vector_id (int): ID of the vector to retrieve.

        Returns:
            dict: Retrieved vector.
        """
        result = self.collection.get(ids=[vector_id])
        return self._parse_output(result)[0]

    def list_cols(self):
        """
        List all collections.

        Returns:
            list: List of collection names.
        """
        return self.client.list_collections()

    def delete_col(self, name):
        """
        Delete a collection.

        Args:
            name (str): Name of the collection to delete.
        """
        self.client.delete_collection(name=name)

    def col_info(self, name):
        """
        Get information about a collection.

        Args:
            name (str): Name of the collection.

        Returns:
            dict: Collection information.
        """
        return self.client.get_collection(name=name)

    def list(self, name, filters=None, limit=100):
        """
        List all vectors in a collection.

        Args:
            name (str): Name of the collection.
            filters (dict, optional): Filters to apply to the list. Defaults to None.
            limit (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            list: List of vectors.
        """
        array = [[0 for _ in range(1536)] for _ in range(1536)]
        results = self.collection.query(query_embeddings=array, where=filters, n_results=limit)
        return [self._parse_output(results)]