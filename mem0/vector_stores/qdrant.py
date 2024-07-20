import os
import shutil
import logging
from typing import Optional

from pydantic import BaseModel, Field
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


class QdrantConfig(BaseModel):
    host: Optional[str] = Field(None, description="Host address for Qdrant server")
    port: Optional[int] = Field(None, description="Port for Qdrant server")
    path: Optional[str] = Field(None, description="Path for local Qdrant database")


class Qdrant(VectorStoreBase):
    def __init__(
        self,
        client=None,
        host="localhost",
        port=6333,
        path=None,
        url=None,
        api_key=None,
    ):
        """
        Initialize the Qdrant vector store.

        Args:
            client (QdrantClient, optional): Existing Qdrant client instance. Defaults to None.
            host (str, optional): Host address for Qdrant server. Defaults to "localhost".
            port (int, optional): Port for Qdrant server. Defaults to 6333.
            path (str, optional): Path for local Qdrant database. Defaults to None.
            url (str, optional): Full URL for Qdrant server. Defaults to None.
            api_key (str, optional): API key for Qdrant server. Defaults to None.
        """
        if client:
            self.client = client
        else:
            params = {}
            if path:
                params["path"] = path
                if os.path.exists(path) and os.path.isdir(path):
                    shutil.rmtree(path)
            if api_key:
                params["api_key"] = api_key
            if url:
                params["url"] = url
            if host and port:
                params["host"] = host
                params["port"] = port
            self.client = QdrantClient(**params)

    def create_col(self, name, vector_size, distance=Distance.COSINE):
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
            if collection.name == name:
                logging.debug(f"Collection {name} already exists. Skipping creation.")
                return

        self.client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=vector_size, distance=distance),
        )

    def insert(self, name, vectors, payloads=None, ids=None):
        """
        Insert vectors into a collection.

        Args:
            name (str): Name of the collection.
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
        self.client.upsert(collection_name=name, points=points)

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
        query_filter = self._create_filter(filters) if filters else None
        hits = self.client.search(
            collection_name=name,
            query_vector=query,
            query_filter=query_filter,
            limit=limit,
        )
        return hits

    def delete(self, name, vector_id):
        """
        Delete a vector by ID.

        Args:
            name (str): Name of the collection.
            vector_id (int): ID of the vector to delete.
        """
        self.client.delete(
            collection_name=name,
            points_selector=PointIdsList(
                points=[vector_id],
            ),
        )

    def update(self, name, vector_id, vector=None, payload=None):
        """
        Update a vector and its payload.

        Args:
            name (str): Name of the collection.
            vector_id (int): ID of the vector to update.
            vector (list, optional): Updated vector. Defaults to None.
            payload (dict, optional): Updated payload. Defaults to None.
        """
        point = PointStruct(id=vector_id, vector=vector, payload=payload)
        self.client.upsert(collection_name=name, points=[point])

    def get(self, name, vector_id):
        """
        Retrieve a vector by ID.

        Args:
            name (str): Name of the collection.
            vector_id (int): ID of the vector to retrieve.

        Returns:
            dict: Retrieved vector.
        """
        result = self.client.retrieve(
            collection_name=name, ids=[vector_id], with_payload=True
        )
        return result[0] if result else None

    def list_cols(self):
        """
        List all collections.

        Returns:
            list: List of collection names.
        """
        return self.client.get_collections()

    def delete_col(self, name):
        """
        Delete a collection.

        Args:
            name (str): Name of the collection to delete.
        """
        self.client.delete_collection(collection_name=name)

    def col_info(self, name):
        """
        Get information about a collection.

        Args:
            name (str): Name of the collection.

        Returns:
            dict: Collection information.
        """
        return self.client.get_collection(collection_name=name)

    def list(self, name, filters=None, limit=100):
        """
        List all vectors in a collection.

        Args:
            name (str): Name of the collection.
            limit (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            list: List of vectors.
        """
        query_filter = self._create_filter(filters) if filters else None
        result = self.client.scroll(
            collection_name=name,
            scroll_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return result
