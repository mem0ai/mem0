import logging
from typing import Dict, List, Optional

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

try:
    from upstash_vector import Index
except ImportError:
    raise ImportError("The 'upstash_vector' library is required. Please install it using 'pip install upstash_vector'.")


logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # is None for `get` method
    payload: Optional[Dict]  # metadata


class UpstashVector(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        url: Optional[str] = None,
        token: Optional[str] = None,
        client: Optional[Index] = None,
        enable_embeddings: bool = False,
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

        self.collection_name = collection_name

        self.enable_embeddings = enable_embeddings

    def insert(
        self,
        vectors: List[list],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
    ):
        """
        Insert vectors

        Args:
            vectors (list): List of vectors to insert.
            payloads (list, optional): List of payloads corresponding to vectors. These will be passed as metadatas to the Upstash Vector client. Defaults to None.
            ids (list, optional): List of IDs corresponding to vectors. Defaults to None.
        """
        logger.info(f"Inserting {len(vectors)} vectors into namespace {self.collection_name}")

        if self.enable_embeddings:
            if not payloads or any("data" not in m or m["data"] is None for m in payloads):
                raise ValueError("When embeddings are enabled, all payloads must contain a 'data' field.")
            processed_vectors = [
                {
                    "id": ids[i] if ids else None,
                    "data": payloads[i]["data"],
                    "metadata": payloads[i],
                }
                for i, v in enumerate(vectors)
            ]
        else:
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
            namespace=self.collection_name,
        )

    def _stringify(self, x):
        return f'"{x}"' if isinstance(x, str) else x

    def search(
        self,
        query: str,
        vectors: List[list],
        limit: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[OutputData]:
        """
        Search for similar vectors.

        Args:
            query (list): Query vector.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search.

        Returns:
            List[OutputData]: Search results.
        """

        filters_str = " AND ".join([f"{k} = {self._stringify(v)}" for k, v in filters.items()]) if filters else None

        response = []

        if self.enable_embeddings:
            response = self.client.query(
                data=query,
                top_k=limit,
                filter=filters_str or "",
                include_metadata=True,
                namespace=self.collection_name,
            )
        else:
            queries = [
                {
                    "vector": v,
                    "top_k": limit,
                    "filter": filters_str or "",
                    "include_metadata": True,
                    "namespace": self.collection_name,
                }
                for v in vectors
            ]
            responses = self.client.query_many(queries=queries)
            # flatten
            response = [res for res_list in responses for res in res_list]

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
            ids=[str(vector_id)],
            namespace=self.collection_name,
        )

    def update(
        self,
        vector_id: int,
        vector: Optional[list] = None,
        payload: Optional[dict] = None,
    ):
        """
        Update a vector and its payload.

        Args:
            vector_id (int): ID of the vector to update.
            vector (list, optional): Updated vector. Defaults to None.
            payload (dict, optional): Updated payload. Defaults to None.
        """
        self.client.update(
            id=str(vector_id),
            vector=vector,
            data=payload.get("data") if payload else None,
            metadata=payload,
            namespace=self.collection_name,
        )

    def get(self, vector_id: int) -> Optional[OutputData]:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (int): ID of the vector to retrieve.

        Returns:
            dict: Retrieved vector.
        """
        response = self.client.fetch(
            ids=[str(vector_id)],
            namespace=self.collection_name,
            include_metadata=True,
        )
        if len(response) == 0:
            return None
        vector = response[0]
        if not vector:
            return None
        return OutputData(id=vector.id, score=None, payload=vector.metadata)

    def list(self, filters: Optional[Dict] = None, limit: int = 100) -> List[List[OutputData]]:
        """
        List all memories.
        Args:
            filters (Dict, optional): Filters to apply to the search. Defaults to None.
            limit (int, optional): Number of results to return. Defaults to 100.
        Returns:
            List[OutputData]: Search results.
        """
        filters_str = " AND ".join([f"{k} = {self._stringify(v)}" for k, v in filters.items()]) if filters else None

        info = self.client.info()
        ns_info = info.namespaces.get(self.collection_name)

        if not ns_info or ns_info.vector_count == 0:
            return [[]]

        random_vector = [1.0] * self.client.info().dimension

        results, query = self.client.resumable_query(
            vector=random_vector,
            filter=filters_str or "",
            include_metadata=True,
            namespace=self.collection_name,
            top_k=100,
        )
        with query:
            while True:
                if len(results) >= limit:
                    break
                res = query.fetch_next(100)
                if not res:
                    break
                results.extend(res)

        parsed_result = [
            OutputData(
                id=res.id,
                score=res.score,
                payload=res.metadata,
            )
            for res in results
        ]
        return [parsed_result]

    def create_col(self, name, vector_size, distance):
        """
        Upstash Vector has namespaces instead of collections. A namespace is created when the first vector is inserted.

        This method is a placeholder to maintain the interface.
        """
        pass

    def list_cols(self) -> List[str]:
        """
        Lists all namespaces in the Upstash Vector index.
        Returns:
            List[str]: List of namespaces.
        """
        return self.client.list_namespaces()

    def delete_col(self):
        """
        Delete the namespace and all vectors in it.
        """
        self.client.reset(namespace=self.collection_name)
        pass

    def col_info(self):
        """
        Return general information about the Upstash Vector index.

        - Total number of vectors across all namespaces
        - Total number of vectors waiting to be indexed across all namespaces
        - Total size of the index on disk in bytes
        - Vector dimension
        - Similarity function used
        - Per-namespace vector and pending vector counts
        """
        return self.client.info()
