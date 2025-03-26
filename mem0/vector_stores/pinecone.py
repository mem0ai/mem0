import logging
import os
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel

try:
    from pinecone import Pinecone, PodSpec, ServerlessSpec
    from pinecone.data.dataclasses.vector import Vector
except ImportError:
    raise ImportError(
        "Pinecone requires extra dependencies. Install with `pip install pinecone pinecone-text`"
    ) from None

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # distance
    payload: Optional[Dict]  # metadata


class PineconeDB(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        embedding_model_dims: int,
        client: Optional["Pinecone"],
        api_key: Optional[str],
        environment: Optional[str],
        serverless_config: Optional[Dict[str, Any]],
        pod_config: Optional[Dict[str, Any]],
        hybrid_search: bool,
        metric: str,
        batch_size: int,
        extra_params: Optional[Dict[str, Any]],
    ):
        """
        Initialize the Pinecone vector store.

        Args:
            collection_name (str): Name of the index/collection.
            embedding_model_dims (int): Dimensions of the embedding model.
            client (Pinecone, optional): Existing Pinecone client instance. Defaults to None.
            api_key (str, optional): API key for Pinecone. Defaults to None.
            environment (str, optional): Pinecone environment. Defaults to None.
            serverless_config (Dict, optional): Configuration for serverless deployment. Defaults to None.
            pod_config (Dict, optional): Configuration for pod-based deployment. Defaults to None.
            hybrid_search (bool, optional): Whether to enable hybrid search. Defaults to False.
            metric (str, optional): Distance metric for vector similarity. Defaults to "cosine".
            batch_size (int, optional): Batch size for operations. Defaults to 100.
            extra_params (Dict, optional): Additional parameters for Pinecone client. Defaults to None.
        """
        if client:
            self.client = client
        else:
            api_key = api_key or os.environ.get("PINECONE_API_KEY")
            if not api_key:
                raise ValueError(
                    "Pinecone API key must be provided either as a parameter or as an environment variable"
                )

            params = extra_params or {}
            self.client = Pinecone(api_key=api_key, **params)

        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.environment = environment
        self.serverless_config = serverless_config
        self.pod_config = pod_config
        self.hybrid_search = hybrid_search
        self.metric = metric
        self.batch_size = batch_size

        self.sparse_encoder = None
        if self.hybrid_search:
            try:
                from pinecone_text.sparse import BM25Encoder

                logger.info("Initializing BM25Encoder for sparse vectors...")
                self.sparse_encoder = BM25Encoder.default()
            except ImportError:
                logger.warning("pinecone-text not installed. Hybrid search will be disabled.")
                self.hybrid_search = False

        self.create_col(embedding_model_dims, metric)

    def create_col(self, vector_size: int, metric: str = "cosine"):
        """
        Create a new index/collection.

        Args:
            vector_size (int): Size of the vectors to be stored.
            metric (str, optional): Distance metric for vector similarity. Defaults to "cosine".
        """
        existing_indexes = self.list_cols().names()

        if self.collection_name in existing_indexes:
            logging.debug(f"Index {self.collection_name} already exists. Skipping creation.")
            self.index = self.client.Index(self.collection_name)
            return

        if self.serverless_config:
            spec = ServerlessSpec(**self.serverless_config)
        elif self.pod_config:
            spec = PodSpec(**self.pod_config)
        else:
            spec = ServerlessSpec(cloud="aws", region="us-west-2")

        self.client.create_index(
            name=self.collection_name,
            dimension=vector_size,
            metric=metric,
            spec=spec,
        )

        self.index = self.client.Index(self.collection_name)

    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[Union[str, int]]] = None,
    ):
        """
        Insert vectors into an index.

        Args:
            vectors (list): List of vectors to insert.
            payloads (list, optional): List of payloads corresponding to vectors. Defaults to None.
            ids (list, optional): List of IDs corresponding to vectors. Defaults to None.
        """
        logger.info(f"Inserting {len(vectors)} vectors into index {self.collection_name}")
        items = []

        for idx, vector in enumerate(vectors):
            item_id = str(ids[idx]) if ids is not None else str(idx)
            payload = payloads[idx] if payloads else {}

            vector_record = {"id": item_id, "values": vector, "metadata": payload}

            if self.hybrid_search and self.sparse_encoder and "text" in payload:
                sparse_vector = self.sparse_encoder.encode_documents(payload["text"])
                vector_record["sparse_values"] = sparse_vector

            items.append(vector_record)

            if len(items) >= self.batch_size:
                self.index.upsert(vectors=items)
                items = []

        if items:
            self.index.upsert(vectors=items)

    def _parse_output(self, data: Dict) -> List[OutputData]:
        """
        Parse the output data from Pinecone search results.

        Args:
            data (Dict): Output data from Pinecone query.

        Returns:
            List[OutputData]: Parsed output data.
        """
        if isinstance(data, Vector):
            result = OutputData(
                id=data.id,
                score=0.0,
                payload=data.metadata,
            )
            return result
        else:
            result = []
            for match in data:
                entry = OutputData(
                    id=match.get("id"),
                    score=match.get("score"),
                    payload=match.get("metadata"),
                )
                result.append(entry)

            return result

    def _create_filter(self, filters: Optional[Dict]) -> Dict:
        """
        Create a filter dictionary from the provided filters.
        """
        if not filters:
            return {}

        pinecone_filter = {}

        for key, value in filters.items():
            if isinstance(value, dict) and "gte" in value and "lte" in value:
                pinecone_filter[key] = {"$gte": value["gte"], "$lte": value["lte"]}
            else:
                pinecone_filter[key] = {"$eq": value}

        return pinecone_filter

    def search(
        self, query: str, vectors: List[float], limit: int = 5, filters: Optional[Dict] = None
    ) -> List[OutputData]:
        """
        Search for similar vectors.

        Args:
            query (str): Query.
            vectors (list): List of vectors to search.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """
        filter_dict = self._create_filter(filters) if filters else None

        query_params = {
            "vector": vectors,
            "top_k": limit,
            "include_metadata": True,
            "include_values": False,
        }

        if filter_dict:
            query_params["filter"] = filter_dict

        if self.hybrid_search and self.sparse_encoder and "text" in filters:
            query_text = filters.get("text")
            if query_text:
                sparse_vector = self.sparse_encoder.encode_queries(query_text)
                query_params["sparse_vector"] = sparse_vector

        response = self.index.query(**query_params)

        results = self._parse_output(response.matches)
        return results

    def delete(self, vector_id: Union[str, int]):
        """
        Delete a vector by ID.

        Args:
            vector_id (Union[str, int]): ID of the vector to delete.
        """
        self.index.delete(ids=[str(vector_id)])

    def update(self, vector_id: Union[str, int], vector: Optional[List[float]] = None, payload: Optional[Dict] = None):
        """
        Update a vector and its payload.

        Args:
            vector_id (Union[str, int]): ID of the vector to update.
            vector (list, optional): Updated vector. Defaults to None.
            payload (dict, optional): Updated payload. Defaults to None.
        """
        item = {
            "id": str(vector_id),
        }

        if vector is not None:
            item["values"] = vector

        if payload is not None:
            item["metadata"] = payload

            if self.hybrid_search and self.sparse_encoder and "text" in payload:
                sparse_vector = self.sparse_encoder.encode_documents(payload["text"])
                item["sparse_values"] = sparse_vector

        self.index.upsert(vectors=[item])

    def get(self, vector_id: Union[str, int]) -> OutputData:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (Union[str, int]): ID of the vector to retrieve.

        Returns:
            dict: Retrieved vector or None if not found.
        """
        try:
            response = self.index.fetch(ids=[str(vector_id)])
            if str(vector_id) in response.vectors:
                return self._parse_output(response.vectors[str(vector_id)])
            return None
        except Exception as e:
            logger.error(f"Error retrieving vector {vector_id}: {e}")
            return None

    def list_cols(self):
        """
        List all indexes/collections.

        Returns:
            list: List of index information.
        """
        return self.client.list_indexes()

    def delete_col(self):
        """Delete an index/collection."""
        try:
            self.client.delete_index(self.collection_name)
            logger.info(f"Index {self.collection_name} deleted successfully")
        except Exception as e:
            logger.error(f"Error deleting index {self.collection_name}: {e}")

    def col_info(self) -> Dict:
        """
        Get information about an index/collection.

        Returns:
            dict: Index information.
        """
        return self.client.describe_index(self.collection_name)

    def list(self, filters: Optional[Dict] = None, limit: int = 100) -> List[OutputData]:
        """
        List vectors in an index with optional filtering.

        Args:
            filters (dict, optional): Filters to apply to the list. Defaults to None.
            limit (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            dict: List of vectors with their metadata.
        """
        filter_dict = self._create_filter(filters) if filters else None

        stats = self.index.describe_index_stats()
        dimension = stats.dimension

        zero_vector = [0.0] * dimension

        query_params = {
            "vector": zero_vector,
            "top_k": limit,
            "include_metadata": True,
            "include_values": True,
        }

        if filter_dict:
            query_params["filter"] = filter_dict

        try:
            response = self.index.query(**query_params)
            response = response.to_dict()
            results = self._parse_output(response["matches"])
            return [results]
        except Exception as e:
            logger.error(f"Error listing vectors: {e}")
            return {"points": [], "next_page_token": None}

    def count(self) -> int:
        """
        Count number of vectors in the index.

        Returns:
            int: Total number of vectors.
        """
        stats = self.index.describe_index_stats()
        return stats.total_vector_count

    def reset(self):
        """
        Reset the index by deleting and recreating it.
        """
        self.delete_col()
        self.create_col(self.embedding_model_dims, self.metric)
