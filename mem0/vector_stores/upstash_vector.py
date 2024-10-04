import logging
from typing import Dict, List, Optional

from pydantic import BaseModel
from upstash_vector import Index

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # is None for `get` method
    payload: Optional[Dict]  # metadata


class UpstashVector(VectorStoreBase):
    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[int] = None,
        client: Optional[Index] = None,
        namespace: Optional[str] = None,
    ):
        """
        Initialize the UpstashVector vector store.

        Args:
            url (str, optional): URL for Upstash Vector index. Defaults to None.
            token (int, optional): Token for Upstash Vector index. Defaults to None.
            client (Index, optional): Existing `upstash_vector.Index` client instance. Defaults to None.
            namespace (str, optional): Default namespace for the index. Defaults to None.
        """
        if client:
            self.client = client
        elif url and token:
            self.client = Index(url, token)
        else:
            raise ValueError("Either a client or URL and token must be provided.")

        if namespace is None:
            self.namespace = ""
        else:
            self.namespace = namespace

    def create_col(self):
        """
        Upstash Vector does not have collections. A single vector database only contains one size of vectors.
        """

        raise NotImplementedError(
            "Upstash Vector does not have collections. A single vector database only contains one size of vectors."
        )

    def insert(self, vectors: list, payloads: list = None, ids: list = None):
        """
        Insert vectors

        Args:
            vectors (list): List of vectors to insert.
            payloads (list, optional): List of payloads corresponding to vectors. These will be passed as metadatas to the Upstash Vector client. Defaults to None.
            ids (list, optional): List of IDs corresponding to vectors. Defaults to None.
        """
        logger.info(f"Inserting {len(vectors)} vectors into namespace {self.namespace}")
        processed_vectors = [
            {
                "id": ids[i] if ids else None,
                "vector": vectors[i],
                "metadata": payloads[i] if payloads else None,
            }
            for i, v in enumerate(vectors)
        ]
        self.client.upsert(
            vectors=processed_vectors,
            namespace=self.namespace,
        )

    def search(self, query: list, limit: int = 5, filters: Dict = None) -> List[OutputData]:
        """
        Search for similar vectors.

        Args:
            query (list): Query vector.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search.

        Returns:
            List[OutputData]: Search results.
        """

        def stringify(x):
            return f'"{x}"' if isinstance(x, str) else x

        filters_str = " AND ".join([f"{k} = {stringify(v)}" for k, v in filters.items()]) if filters else None

        response = self.client.query(
            vector=query,
            top_k=limit,
            filter=filters_str,
            include_metadata=True,
            namespace=self.namespace,
        )
        print("res", response)
        return [
            OutputData(
                id=res.id,
                score=res.score,
                payload=res.metadata,
            )
            for res in response
        ]

    def delete(self, vector_id: int):
        """
        Delete a vector by ID.

        Args:
            vector_id (int): ID of the vector to delete.
        """
        self.client.delete(
            ids=[vector_id],
            namespace=self.namespace,
        )

    def update(self, vector_id: int, vector: list = None, payload: dict = None):
        """
        Update a vector and its payload.

        Args:
            vector_id (int): ID of the vector to update.
            vector (list, optional): Updated vector. Defaults to None.
            payload (dict, optional): Updated payload. Defaults to None.
        """
        self.client.update(
            id=vector_id,
            vector=vector,
            metadata=payload,
            namespace=self.namespace,
        )

    def get(self, vector_id: int) -> dict:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (int): ID of the vector to retrieve.

        Returns:
            dict: Retrieved vector.
        """
        response = self.client.fetch(
            ids=[vector_id],
            namespace=self.namespace,
            include_metadata=True,
        )
        print(response, response[0].id)
        if len(response) == 0:
            return None
        return OutputData(
            id=response[0].id,
            score=None,
            payload=response[0].metadata,
        )

    def list_cols(self) -> list:
        """
        Upstash Vector does not have collections. A single vector database only contains one size of vectors.
        """
        raise NotImplementedError(
            "Upstash Vector does not have collections. A single vector database only contains one size of vectors."
        )

    def delete_col(self):
        """
        Upstash Vector does not have collections. A single vector database only contains one size of vectors.
        """
        raise NotImplementedError(
            "Upstash Vector does not have collections. A single vector database only contains one size of vectors."
        )

    def col_info(self) -> dict:
        """
        Upstash Vector does not have collections. A single vector database only contains one size of vectors.
        """
        raise NotImplementedError(
            "Upstash Vector does not have collections. A single vector database only contains one size of vectors."
        )
