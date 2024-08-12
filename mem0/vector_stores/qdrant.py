import os
import shutil
import logging

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointIdsList,
    PointStruct,
    Range,
    VectorParams,
)

from mem0.vector_stores.base import VectorStoreBase


class Qdrant(VectorStoreBase):
    def __init__(
        self,
        collection_name,
        embedding_model_dims,
        client,
        host,
        port,
        path,
        url,
        api_key,
        on_disk
    ):
        """
        Initialize the Qdrant vector store.

        Args:
            client (QdrantClient, optional): Existing Qdrant client instance.
            host (str, optional): Host address for Qdrant server.
            port (int, optional): Port for Qdrant server.
            path (str, optional): Path for local Qdrant database.
            url (str, optional): Full URL for Qdrant server.
            api_key (str, optional): API key for Qdrant server.
            on_disk (bool, optional): Enables persistant storage.
        """
        if client:
            self.client = client
        else:
            params = {}
            if api_key:
                params["api_key"] = api_key
            if url:
                params["url"] = url
            if host and port:
                params["host"] = host
                params["port"] = port
            if not params:
                params["path"] = path
                if not on_disk:
                    if os.path.exists(path) and os.path.isdir(path):
                        shutil.rmtree(path)
            
            self.client = QdrantClient(**params)
        
        self.collection_name = collection_name
        self.create_col(embedding_model_dims, on_disk)

    def create_col(self, vector_size, on_disk, distance=Distance.COSINE):
        """
        Create a new collection.

        Args:
            name (str): Name of the collection.
            vector_size (int): Size of the vectors to be stored.
            distance (Distance, optional): Distance metric for vector similarity. Defaults to Distance.COSINE.
        """
        # Skip creating collection if already exists
        response = self.list_cols()
        for collection in response.collections:
            if collection.name == self.collection_name:
                logging.debug(f"Collection {self.collection_name} already exists. Skipping creation.")
                return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_size, distance=distance, on_disk=on_disk),
        )

    def insert(self, vectors, payloads=None, ids=None):
        """
        Insert vectors into a collection.

        Args:
            vectors (list): List of vectors to insert.
            payloads (list, optional): List of payloads corresponding to vectors. Defaults to None.
            ids (list, optional): List of IDs corresponding to vectors. Defaults to None.
        """
        points = [
            PointStruct(
                id=idx if ids is None else ids[idx],
                vector=vector,
                payload=payloads[idx] if payloads else {},
            )
            for idx, vector in enumerate(vectors)
        ]
        self.client.upsert(collection_name=self.collection_name, points=points)

    def _create_filter(self, filters):
        """
        Create a Filter object from the provided filters.

        Args:
            filters (dict): Filters to apply.

        Returns:
            Filter: The created Filter object.
        """
        conditions = []
        for key, value in filters.items():
            if isinstance(value, dict) and "gte" in value and "lte" in value:
                conditions.append(
                    FieldCondition(
                        key=key, range=Range(gte=value["gte"], lte=value["lte"])
                    )
                )
            else:
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )
        return Filter(must=conditions) if conditions else None

    def search(self, query, limit=5, filters=None):
        """
        Search for similar vectors.

        Args:
            query (list): Query vector.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """
        query_filter = self._create_filter(filters) if filters else None
        hits = self.client.search(
            collection_name=self.collection_name,
            query_vector=query,
            query_filter=query_filter,
            limit=limit,
        )
        return hits

    def delete(self, vector_id):
        """
        Delete a vector by ID.

        Args:
            vector_id (int): ID of the vector to delete.
        """
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=PointIdsList(
                points=[vector_id],
            ),
        )

    def update(self, vector_id, vector=None, payload=None):
        """
        Update a vector and its payload.

        Args:
            vector_id (int): ID of the vector to update.
            vector (list, optional): Updated vector. Defaults to None.
            payload (dict, optional): Updated payload. Defaults to None.
        """
        point = PointStruct(id=vector_id, vector=vector, payload=payload)
        self.client.upsert(collection_name=self.collection_name, points=[point])

    def get(self, vector_id):
        """
        Retrieve a vector by ID.

        Args:
            vector_id (int): ID of the vector to retrieve.

        Returns:
            dict: Retrieved vector.
        """
        result = self.client.retrieve(
            collection_name=self.collection_name, ids=[vector_id], with_payload=True
        )
        return result[0] if result else None

    def list_cols(self):
        """
        List all collections.

        Returns:
            list: List of collection names.
        """
        return self.client.get_collections()

    def delete_col(self):
        """ Delete a collection. """
        self.client.delete_collection(collection_name=self.collection_name)

    def col_info(self):
        """
        Get information about a collection.

        Returns:
            dict: Collection information.
        """
        return self.client.get_collection(collection_name=self.collection_name)

    def list(self, filters=None, limit=100):
        """
        List all vectors in a collection.

        Args:
            limit (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            list: List of vectors.
        """
        query_filter = self._create_filter(filters) if filters else None
        result = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return result
