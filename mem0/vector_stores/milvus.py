import logging
from typing import Dict, Optional

from pydantic import BaseModel

from mem0.configs.vector_stores.milvus import MetricType
from mem0.vector_stores.base import VectorStoreBase

try:
    import pymilvus  # noqa: F401
except ImportError:
    raise ImportError("The 'pymilvus' library is required. Please install it using 'pip install pymilvus'.")

from pymilvus import CollectionSchema, DataType, FieldSchema, Function, FunctionType, MilvusClient

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # distance
    payload: Optional[Dict]  # metadata


class MilvusDB(VectorStoreBase):
    def __init__(
        self,
        url: str,
        token: str,
        collection_name: str,
        embedding_model_dims: int,
        metric_type: MetricType,
        db_name: str,
    ) -> None:
        """Initialize the MilvusDB database.

        Args:
            url (str): Full URL for Milvus/Zilliz server.
            token (str): Token/api_key for Zilliz server / for local setup defaults to None.
            collection_name (str): Name of the collection (defaults to mem0).
            embedding_model_dims (int): Dimensions of the embedding model (defaults to 1536).
            metric_type (MetricType): Metric type for similarity search (defaults to L2).
            db_name (str): Name of the database (defaults to "").
        """
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.metric_type = metric_type
        self.client = MilvusClient(uri=url, token=token, db_name=db_name)
        # Whether this collection has the `text` + `sparse` fields for v3 BM25.
        # Pre-v3 collections lack them; writing a top-level `text` field is rejected.
        self._has_bm25_schema = False
        self.create_col(
            collection_name=self.collection_name,
            vector_size=self.embedding_model_dims,
            metric_type=self.metric_type,
        )

    def create_col(
        self,
        collection_name: str,
        vector_size: int,
        metric_type: MetricType = MetricType.COSINE,
    ) -> None:
        """Create a new collection with index_type AUTOINDEX.

        Args:
            collection_name (str): Name of the collection (defaults to mem0).
            vector_size (int): Dimensions of the embedding model (defaults to 1536).
            metric_type (MetricType, optional): etric type for similarity search. Defaults to MetricType.COSINE.
        """

        if self.client.has_collection(collection_name):
            logger.info(f"Collection {collection_name} already exists. Skipping creation.")
            desc = self.client.describe_collection(collection_name=collection_name)
            field_names = {f.get("name") for f in desc.get("fields", [])}
            self._has_bm25_schema = "text" in field_names and "sparse" in field_names
            if not self._has_bm25_schema:
                logger.warning(
                    f"Collection '{collection_name}' predates v3 hybrid search (no 'text'/'sparse' fields). "
                    "BM25 keyword scoring will be disabled for this collection; semantic search works normally. "
                    "To enable hybrid search, use a fresh collection."
                )
        else:
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=512),
                FieldSchema(name="vectors", dtype=DataType.FLOAT_VECTOR, dim=vector_size),
                FieldSchema(name="metadata", dtype=DataType.JSON),
                # Text field for BM25 full-text search (auto-tokenized by Milvus analyzer)
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535, enable_analyzer=True),
                # Sparse vector field populated automatically by the BM25 function below
                FieldSchema(name="sparse", dtype=DataType.SPARSE_FLOAT_VECTOR),
            ]

            schema = CollectionSchema(fields, enable_dynamic_field=True)

            # Add BM25 function so Milvus auto-generates sparse vectors from the text field
            bm25_function = Function(
                name="bm25",
                input_field_names=["text"],
                output_field_names=["sparse"],
                function_type=FunctionType.BM25,
            )
            schema.add_function(bm25_function)

            index_params = self.client.prepare_index_params()
            index_params.add_index(
                field_name="vectors", metric_type=metric_type, index_type="AUTOINDEX", index_name="vector_index"
            )
            index_params.add_index(
                field_name="sparse",
                index_type="SPARSE_INVERTED_INDEX",
                metric_type="BM25",
                index_name="sparse_index",
            )
            self.client.create_collection(collection_name=collection_name, schema=schema, index_params=index_params)
            self._has_bm25_schema = True

    def insert(self, ids, vectors, payloads, **kwargs: Optional[dict[str, any]]):
        """Insert vectors into a collection.

        Args:
            vectors (List[List[float]]): List of vectors to insert.
            payloads (List[Dict], optional): List of payloads corresponding to vectors.
            ids (List[str], optional): List of IDs corresponding to vectors.
        """
        # Batch insert all records at once for better performance and consistency.
        # Only include the `text` field when the collection's schema has it — legacy
        # collections created pre-v3 reject unknown top-level fields.
        def _build_record(idx, embedding, metadata):
            record = {"id": idx, "vectors": embedding, "metadata": metadata}
            if self._has_bm25_schema:
                # Populate the text field for BM25 sparse search; prefer lemmatized text, fall back to raw data
                record["text"] = (metadata.get("text_lemmatized") or metadata.get("data", ""))[:65535] if metadata else ""
            return record

        data = [_build_record(idx, embedding, metadata) for idx, embedding, metadata in zip(ids, vectors, payloads)]
        self.client.insert(collection_name=self.collection_name, data=data, **kwargs)

    def _create_filter(self, filters: dict):
        """Prepare filters for efficient query.

        Args:
            filters (dict): filters [user_id, agent_id, run_id]

        Returns:
            str: formated filter.
        """
        operands = []
        for key, value in filters.items():
            if isinstance(value, str):
                operands.append(f'(metadata["{key}"] == "{value}")')
            else:
                operands.append(f'(metadata["{key}"] == {value})')

        return " and ".join(operands)

    def _parse_output(self, data: list):
        """
        Parse the output data.

        Args:
            data (Dict): Output data.

        Returns:
            List[OutputData]: Parsed output data.
        """
        memory = []

        for value in data:
            uid, score, metadata = (
                value.get("id"),
                value.get("distance"),
                value.get("entity", {}).get("metadata"),
            )

            memory_obj = OutputData(id=uid, score=score, payload=metadata)
            memory.append(memory_obj)

        return memory

    def search(self, query: str, vectors: list, top_k: int = 5, filters: dict = None) -> list:
        """
        Search for similar vectors.

        Args:
            query (str): Query.
            vectors (List[float]): Query vector.
            top_k (int, optional): Number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """
        query_filter = self._create_filter(filters) if filters else None
        # v3 collections carry both a dense `vectors` field and a sparse `sparse`
        # field (for BM25), which makes anns_field ambiguous — Milvus rejects the
        # query otherwise with "multiple anns_fields exist". Legacy single-vector
        # collections don't need the hint, so only pass it when the hybrid schema
        # is present.
        search_kwargs = {
            "collection_name": self.collection_name,
            "data": [vectors],
            "limit": top_k,
            "filter": query_filter,
            "output_fields": ["*"],
        }
        if self._has_bm25_schema:
            search_kwargs["anns_field"] = "vectors"
        hits = self.client.search(**search_kwargs)
        result = self._parse_output(data=hits[0])
        return result

    def keyword_search(self, query, top_k=5, filters=None):
        """
        Search for memories using BM25-based full-text search via Milvus sparse vector support.

        Milvus 2.5+ supports native BM25 via full-text search with a SPARSE_FLOAT_VECTOR field.
        This method attempts to use that capability. If the collection does not have a sparse
        field configured, it returns None gracefully.

        Args:
            query (str): The text query for keyword-based search.
            top_k (int, optional): Number of results to return. Defaults to 5.
            filters (dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results in the same format as search(), or None if sparse search
                  is not supported on this collection.
        """
        if not self._has_bm25_schema:
            return None
        try:
            query_filter = self._create_filter(filters) if filters else None
            hits = self.client.search(
                collection_name=self.collection_name,
                data=[query],
                anns_field="sparse",
                limit=top_k,
                filter=query_filter,
                output_fields=["*"],
            )
            result = self._parse_output(data=hits[0])
            return result
        except Exception as e:
            logger.debug(f"Keyword search not available for collection {self.collection_name}: {e}")
            return None

    def delete(self, vector_id):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        self.client.delete(collection_name=self.collection_name, ids=vector_id)

    def update(self, vector_id=None, vector=None, payload=None):
        """
        Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (List[float], optional): Updated vector.
            payload (Dict, optional): Updated payload.
        """
        if vector is None or payload is None:
            existing = self.client.get(collection_name=self.collection_name, ids=vector_id)
            if not existing:
                raise ValueError(f"Vector with id {vector_id} not found in collection {self.collection_name}")
            if vector is None:
                vector = existing[0].get("vectors")
                if vector is None:
                    raise ValueError(f"Existing record {vector_id} has no vector data")
            if payload is None:
                payload = existing[0].get("metadata")

        text = ""
        if payload:
            text = (payload.get("text_lemmatized") or payload.get("data", ""))[:65535]
        schema = {"id": vector_id, "vectors": vector, "metadata": payload, "text": text}
        self.client.upsert(collection_name=self.collection_name, data=schema)

    def get(self, vector_id):
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector.
        """
        result = self.client.get(collection_name=self.collection_name, ids=vector_id)
        output = OutputData(
            id=result[0].get("id", None),
            score=None,
            payload=result[0].get("metadata", None),
        )
        return output

    def list_cols(self):
        """
        List all collections.

        Returns:
            List[str]: List of collection names.
        """
        return self.client.list_collections()

    def delete_col(self):
        """Delete a collection."""
        return self.client.drop_collection(collection_name=self.collection_name)

    def col_info(self):
        """
        Get information about a collection.

        Returns:
            Dict[str, Any]: Collection information.
        """
        return self.client.get_collection_stats(collection_name=self.collection_name)

    def list(self, filters: dict = None, top_k: int = 100) -> list:
        """
        List all vectors in a collection.

        Args:
            filters (Dict, optional): Filters to apply to the list.
            top_k (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            List[OutputData]: List of vectors.
        """
        query_filter = self._create_filter(filters) if filters else None
        result = self.client.query(collection_name=self.collection_name, filter=query_filter, limit=top_k)
        memories = []
        for data in result:
            obj = OutputData(id=data.get("id"), score=None, payload=data.get("metadata"))
            memories.append(obj)
        return [memories]

    def reset(self):
        """Reset the index by deleting and recreating it."""
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.create_col(self.collection_name, self.embedding_model_dims, self.metric_type)
