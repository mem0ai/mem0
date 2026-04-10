import logging
import os
import shutil

from qdrant_client import QdrantClient, models
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchExcept,
    MatchText,
    MatchValue,
    PointIdsList,
    PointStruct,
    Range,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class Qdrant(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        embedding_model_dims: int,
        client: QdrantClient = None,
        host: str = None,
        port: int = None,
        path: str = None,
        url: str = None,
        api_key: str = None,
        on_disk: bool = False,
    ):
        """
        Initialize the Qdrant vector store.

        Args:
            collection_name (str): Name of the collection.
            embedding_model_dims (int): Dimensions of the embedding model.
            client (QdrantClient, optional): Existing Qdrant client instance. Defaults to None.
            host (str, optional): Host address for Qdrant server. Defaults to None.
            port (int, optional): Port for Qdrant server. Defaults to None.
            path (str, optional): Path for local Qdrant database. Defaults to None.
            url (str, optional): Full URL for Qdrant server. Defaults to None.
            api_key (str, optional): API key for Qdrant server. Defaults to None.
            on_disk (bool, optional): Enables persistent storage. Defaults to False.
        """
        if client:
            self.client = client
            self.is_local = False
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
                self.is_local = True
                if not on_disk:
                    if os.path.exists(path) and os.path.isdir(path):
                        shutil.rmtree(path)
            else:
                self.is_local = False

            self.client = QdrantClient(**params)

        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.on_disk = on_disk
        self._bm25_encoder = None
        self.create_col(embedding_model_dims, on_disk)

    def _get_bm25_encoder(self):
        """Lazy-load the BM25 sparse text encoder (fastembed)."""
        if self._bm25_encoder is None:
            try:
                from fastembed import SparseTextEmbedding
                self._bm25_encoder = SparseTextEmbedding(model_name="Qdrant/bm25")
                logger.info("BM25 encoder loaded (fastembed Qdrant/bm25)")
            except ImportError:
                logger.warning("fastembed not installed — BM25 keyword search disabled. Install with: pip install fastembed")
                self._bm25_encoder = False  # sentinel: tried and failed
            except Exception as e:
                logger.warning(f"Failed to load BM25 encoder: {e}")
                self._bm25_encoder = False
        return self._bm25_encoder if self._bm25_encoder is not False else None

    def _encode_bm25(self, text: str) -> SparseVector | None:
        """Encode text into a BM25 sparse vector."""
        encoder = self._get_bm25_encoder()
        if encoder is None:
            return None
        try:
            results = list(encoder.embed([text]))
            if results:
                sparse = results[0]
                return SparseVector(
                    indices=sparse.indices.tolist(),
                    values=sparse.values.tolist(),
                )
        except Exception as e:
            logger.debug(f"BM25 encoding failed: {e}")
        return None

    def create_col(self, vector_size: int, on_disk: bool, distance: Distance = Distance.COSINE):
        """
        Create a new collection with dense vectors and BM25 sparse vectors.

        Args:
            vector_size (int): Size of the vectors to be stored.
            on_disk (bool): Enables persistent storage.
            distance (Distance, optional): Distance metric for vector similarity. Defaults to Distance.COSINE.
        """
        # Skip creating collection if already exists
        response = self.list_cols()
        for collection in response.collections:
            if collection.name == self.collection_name:
                logger.debug(f"Collection {self.collection_name} already exists. Skipping creation.")
                self._create_filter_indexes()
                return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=vector_size, distance=distance, on_disk=on_disk),
            sparse_vectors_config={
                "bm25": SparseVectorParams(
                    modifier=models.Modifier.IDF,
                ),
            },
        )
        self._create_filter_indexes()

    def _create_filter_indexes(self):
        """Create indexes for commonly used filter fields to enable filtering."""
        # Only create payload indexes for remote Qdrant servers
        if self.is_local:
            logger.debug("Skipping payload index creation for local Qdrant (not supported)")
            return

        common_fields = ["user_id", "agent_id", "run_id", "actor_id"]

        for field in common_fields:
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema="keyword"
                )
                logger.info(f"Created index for {field} in collection {self.collection_name}")
            except Exception as e:
                logger.debug(f"Index for {field} might already exist: {e}")

    def insert(self, vectors: list, payloads: list = None, ids: list = None):
        """
        Insert vectors into a collection, including BM25 sparse vectors
        computed from the text_lemmatized payload field.

        Args:
            vectors (list): List of vectors to insert.
            payloads (list, optional): List of payloads corresponding to vectors. Defaults to None.
            ids (list, optional): List of IDs corresponding to vectors. Defaults to None.
        """
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")
        points = []
        for idx, vector in enumerate(vectors):
            payload = payloads[idx] if payloads else {}
            point_id = idx if ids is None else ids[idx]

            # Build named vectors: dense + optional BM25 sparse
            named_vectors = {"": vector}
            text_for_bm25 = payload.get("text_lemmatized") or payload.get("data", "")
            if text_for_bm25:
                sparse = self._encode_bm25(text_for_bm25)
                if sparse is not None:
                    named_vectors["bm25"] = sparse

            points.append(PointStruct(id=point_id, vector=named_vectors, payload=payload))

        self.client.upsert(collection_name=self.collection_name, points=points)

    def _create_filter(self, filters: dict) -> Filter:
        """
        Create a Filter object from the provided filters.

        Supports advanced operators produced by ``_process_metadata_filters``:
        - Simple equality:  ``{"key": "value"}``
        - Operator dicts:   ``{"key": {"eq": …, "ne": …, "in": …, "nin": …,
                                        "gt": …, "gte": …, "lt": …, "lte": …,
                                        "contains": …, "icontains": …}}``
        - Range shorthand:  ``{"key": {"gte": …, "lte": …}}``
        - Logical:          ``{"$or": [...]}, {"$not": [...]}``

        Args:
            filters (dict): Filters to apply.

        Returns:
            Filter: The created Filter object.
        """
        if not filters:
            return None

        must = []
        should = []
        must_not = []

        for key, value in filters.items():
            # ── Logical combinators ──────────────────────────────
            if key == "$or":
                for sub_filter in value:
                    inner = self._create_filter(sub_filter)
                    if inner and inner.must:
                        should.extend(inner.must)
                continue
            if key == "$not":
                for sub_filter in value:
                    inner = self._create_filter(sub_filter)
                    if inner and inner.must:
                        must_not.extend(inner.must)
                continue

            # ── Operator dict ────────────────────────────────────
            if isinstance(value, dict):
                # Range shorthand: {"gte": …, "lte": …}
                if "gte" in value and "lte" in value and len(value) == 2:
                    must.append(FieldCondition(key=key, range=Range(gte=value["gte"], lte=value["lte"])))
                    continue

                for op, operand in value.items():
                    if op == "eq":
                        must.append(FieldCondition(key=key, match=MatchValue(value=operand)))
                    elif op == "ne":
                        must_not.append(FieldCondition(key=key, match=MatchValue(value=operand)))
                    elif op == "in":
                        must.append(FieldCondition(key=key, match=MatchAny(any=operand)))
                    elif op == "nin":
                        must.append(FieldCondition(key=key, match=MatchExcept(**{"except": operand})))
                    elif op in ("gt", "gte", "lt", "lte"):
                        must.append(FieldCondition(key=key, range=Range(**{op: operand})))
                    elif op in ("contains", "icontains"):
                        must.append(FieldCondition(key=key, match=MatchText(text=operand)))
                    else:
                        # Unknown operator — treat as simple equality on the
                        # whole dict value (backward-compatible fallback).
                        must.append(FieldCondition(key=key, match=MatchValue(value=value)))
                        break  # only add once for the whole dict
                continue

            # ── Simple equality ───────────────────────────────────
            must.append(FieldCondition(key=key, match=MatchValue(value=value)))

        return Filter(
            must=must or None,
            should=should or None,
            must_not=must_not or None,
        )

    def search(self, query: str, vectors: list, limit: int = 5, filters: dict = None) -> list:
        """
        Search for similar vectors.

        Args:
            query (str): Query.
            vectors (list): Query vector.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """
        query_filter = self._create_filter(filters) if filters else None
        hits = self.client.query_points(
            collection_name=self.collection_name,
            query=vectors,
            query_filter=query_filter,
            limit=limit,
        )
        return hits.points

    def search_batch(self, queries: list, vectors_list: list, limit: int = 1, filters: dict = None):
        """Batch search using Qdrant's query_batch_points for efficiency."""
        query_filter = self._create_filter(filters) if filters else None
        requests = [
            models.QueryRequest(query=vec, filter=query_filter, limit=limit)
            for vec in vectors_list
        ]
        try:
            results = self.client.query_batch_points(
                collection_name=self.collection_name,
                requests=requests,
            )
            return [r.points for r in results]
        except Exception as e:
            logger.warning(f"Batch search failed, falling back to sequential: {e}")
            return [self.search(q, v, limit=limit, filters=filters) for q, v in zip(queries, vectors_list)]

    def keyword_search(self, query, limit=5, filters=None):
        """
        Search using BM25 sparse vectors for keyword-based retrieval.

        Args:
            query (str): The search query text.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results, or None if BM25 is not available.
        """
        sparse_query = self._encode_bm25(query)
        if sparse_query is None:
            return None

        try:
            query_filter = self._create_filter(filters) if filters else None
            hits = self.client.query_points(
                collection_name=self.collection_name,
                query=sparse_query,
                using="bm25",
                query_filter=query_filter,
                limit=limit,
            )
            return hits.points
        except Exception as e:
            logger.debug(f"BM25 keyword search failed: {e}")
            return None

    def delete(self, vector_id: int):
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

    def update(self, vector_id: int, vector: list = None, payload: dict = None):
        """
        Update a vector and its payload.

        Args:
            vector_id (int): ID of the vector to update.
            vector (list, optional): Updated vector. Defaults to None.
            payload (dict, optional): Updated payload. Defaults to None.
        """
        # Build named vectors with BM25 if payload has text
        named_vectors = {"": vector} if vector else vector
        if payload and vector:
            text_for_bm25 = payload.get("text_lemmatized") or payload.get("data", "")
            if text_for_bm25:
                sparse = self._encode_bm25(text_for_bm25)
                if sparse is not None:
                    named_vectors["bm25"] = sparse

        point = PointStruct(id=vector_id, vector=named_vectors, payload=payload)
        self.client.upsert(collection_name=self.collection_name, points=[point])

    def get(self, vector_id: int) -> dict:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (int): ID of the vector to retrieve.

        Returns:
            dict: Retrieved vector.
        """
        result = self.client.retrieve(collection_name=self.collection_name, ids=[vector_id], with_payload=True)
        return result[0] if result else None

    def list_cols(self) -> list:
        """
        List all collections.

        Returns:
            list: List of collection names.
        """
        return self.client.get_collections()

    def delete_col(self):
        """Delete a collection."""
        self.client.delete_collection(collection_name=self.collection_name)

    def col_info(self) -> dict:
        """
        Get information about a collection.

        Returns:
            dict: Collection information.
        """
        return self.client.get_collection(collection_name=self.collection_name)

    def list(self, filters: dict = None, limit: int = 100) -> list:
        """
        List all vectors in a collection.

        Args:
            filters (dict, optional): Filters to apply to the list. Defaults to None.
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

    def reset(self):
        """Reset the index by deleting and recreating it."""
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.create_col(self.embedding_model_dims, self.on_disk)
