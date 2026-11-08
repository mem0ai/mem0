import logging
from typing import Dict, List, Optional

from pydantic import BaseModel

try:
    from langchain_community.vectorstores import VectorStore
except ImportError:
    raise ImportError(
        "The 'langchain_community' library is required. Please install it using 'pip install langchain_community'."
    )

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # similarity score
    payload: Optional[Dict]  # metadata


# Methods that accept a pre-computed embedding and return (Document, float) pairs.
# Tried in order; first match wins. Not part of the base VectorStore contract,
# but exposed by several concrete implementations.
_SCORED_BY_VECTOR_METHODS = [
    "similarity_search_by_vector_with_relevance_scores",  # Chroma
    "similarity_search_with_score_by_vector",  # FAISS, Qdrant
    "similarity_search_by_vector_with_score",  # Pinecone, YDB
]


class Langchain(VectorStoreBase):
    def __init__(self, client: VectorStore, collection_name: str = "mem0"):
        self.client = client
        self.collection_name = collection_name

    def _uses_distance_scores(self, method_name: str) -> bool:
        """Return whether the client's scored method reports a distance."""
        distance_strategy = getattr(self.client, "distance_strategy", None)
        strategy_name = getattr(distance_strategy, "value", distance_strategy)
        if str(strategy_name).upper() in {
            "EUCLIDEAN_DISTANCE",
            "EUCLIDEAN",
            "EUCLID",
            "L2",
        }:
            return True

        # Chroma exposes raw distances through a method whose name includes
        # "relevance". Its metric is stored on the collection instead of on
        # the vector store, and its default metric is L2.
        collection = getattr(self.client, "_collection", None)
        if method_name == "similarity_search_by_vector_with_relevance_scores":
            return collection is not None

        metadata = getattr(collection, "metadata", None)
        return isinstance(metadata, dict) and "hnsw:space" in metadata

    def _normalize_score(self, score: float, method_name: str) -> float:
        """Convert a raw distance into a higher-is-better score."""
        if not self._uses_distance_scores(method_name):
            return float(score)

        select_relevance_score_fn = getattr(self.client, "_select_relevance_score_fn", None)
        relevance_score_fn = None
        if callable(select_relevance_score_fn):
            try:
                relevance_score_fn = select_relevance_score_fn()
            except (NotImplementedError, TypeError, ValueError):
                pass

        if relevance_score_fn is None:
            relevance_score_fn = getattr(self.client, "relevance_score_fn", None)

        if relevance_score_fn is None:
            relevance_score_fn = getattr(self.client, "override_relevance_score_fn", None)

        if callable(relevance_score_fn):
            try:
                return float(relevance_score_fn(score))
            except (TypeError, ValueError):
                pass

        # Keep the adapter's documented score contract even for a custom
        # distance-based client that does not expose a normalizer.
        return 1.0 / (1.0 + float(score))

    def _parse_output(self, data: Dict) -> List[OutputData]:
        """
        Parse the output data.

        Args:
            data (Dict): Output data or list of Document objects.

        Returns:
            List[OutputData]: Parsed output data.
        """
        # Check if input is a list of Document objects
        if isinstance(data, list) and all(hasattr(doc, "metadata") for doc in data if hasattr(doc, "__dict__")):
            result = []
            for doc in data:
                entry = OutputData(
                    id=getattr(doc, "id", None),
                    score=None,  # Document objects typically don't include scores
                    payload=getattr(doc, "metadata", {}),
                )
                result.append(entry)
            return result

        # Original format handling
        keys = ["ids", "distances", "metadatas"]
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
                score=(distances[i] if isinstance(distances, list) and distances and i < len(distances) else None),
                payload=(metadatas[i] if isinstance(metadatas, list) and metadatas and i < len(metadatas) else None),
            )
            result.append(entry)

        return result

    def create_col(self, name, vector_size=None, distance=None):
        self.collection_name = name
        return self.client

    def insert(
        self, vectors: List[List[float]], payloads: Optional[List[Dict]] = None, ids: Optional[List[str]] = None
    ):
        """
        Insert vectors into the LangChain vectorstore.
        """
        # Check if client has add_embeddings method
        if hasattr(self.client, "add_embeddings"):
            # Some LangChain vectorstores have a direct add_embeddings method
            self.client.add_embeddings(embeddings=vectors, metadatas=payloads, ids=ids)
        else:
            # Fallback to add_texts method
            texts = [payload.get("data", "") for payload in payloads] if payloads else [""] * len(vectors)
            self.client.add_texts(texts=texts, metadatas=payloads, ids=ids)

    def search(self, query: str, vectors: List[List[float]], top_k: int = 5, filters: Optional[Dict] = None):
        """
        Search for similar vectors in LangChain.
        """
        kwargs = {"embedding": vectors, "k": top_k}
        if filters:
            kwargs["filter"] = filters

        # Try methods that return (Document, float) pairs — not in the base contract
        # but available on several concrete implementations.
        for method_name in _SCORED_BY_VECTOR_METHODS:
            method = getattr(self.client, method_name, None)
            if method is None:
                continue
            try:
                results = method(**kwargs)
                return [
                    OutputData(
                        id=getattr(doc, "id", None),
                        score=self._normalize_score(score, method_name),
                        payload=getattr(doc, "metadata", {}),
                    )
                    for doc, score in results
                ]
            except (NotImplementedError, TypeError):
                continue

        # Fallback: similarity_search_by_vector returns List[Document] with no scores.
        # Assign 1.0 so score_and_rank never receives None (None < threshold crashes).
        docs = self.client.similarity_search_by_vector(**kwargs)
        return [
            OutputData(
                id=getattr(doc, "id", None),
                score=1.0,
                payload=getattr(doc, "metadata", {}),
            )
            for doc in docs
        ]

    def delete(self, vector_id):
        """
        Delete a vector by ID.
        """
        self.client.delete(ids=[vector_id])

    def update(self, vector_id, vector=None, payload=None):
        """
        Update a vector and its payload.
        """
        self.delete(vector_id)
        self.insert([vector], [payload], [vector_id])

    def get(self, vector_id):
        """
        Retrieve a vector by ID.
        """
        docs = self.client.get_by_ids([vector_id])
        if docs and len(docs) > 0:
            doc = docs[0]
            return self._parse_output([doc])[0]
        return None

    def list_cols(self):
        """
        List all collections.
        """
        # LangChain doesn't have collections
        return [self.collection_name]

    def delete_col(self):
        """
        Delete a collection.
        """
        logger.warning("Deleting collection")
        if hasattr(self.client, "delete_collection"):
            self.client.delete_collection()
        elif hasattr(self.client, "reset_collection"):
            self.client.reset_collection()
        else:
            self.client.delete(ids=None)

    def col_info(self):
        """
        Get information about a collection.
        """
        return {"name": self.collection_name}

    def list(self, filters=None, top_k=None):
        """
        List all vectors in a collection.
        """
        try:
            if hasattr(self.client, "_collection") and hasattr(self.client._collection, "get"):
                # Convert mem0 filters to Chroma where clause if needed
                where_clause = None
                if filters:
                    # Handle all filters, not just user_id
                    where_clause = filters

                result = self.client._collection.get(where=where_clause, limit=top_k)

                # Convert the result to the expected format
                if result and isinstance(result, dict):
                    return [self._parse_output(result)]
                return []
        except Exception as e:
            logger.error(f"Error listing vectors from Chroma: {e}")
            return []

    def reset(self):
        """Reset the index by deleting and recreating it."""
        logger.warning(f"Resetting collection: {self.collection_name}")
        self.delete_col()
