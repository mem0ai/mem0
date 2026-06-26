import json
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

# Bin name used to store the serialised JSON payload alongside the vector.
_PAYLOAD_BIN = "payload"


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[Dict]


class AerospikeDB(VectorStoreBase):
    """
    Aerospike Vector Search (AVS) vector store for mem0.

    Uses the ``aerospike-vector-search`` Python client to store and retrieve
    memory vectors inside an Aerospike namespace/set backed by an HNSW index.

    Setup
    -----
    1. Run an Aerospike cluster with the AVS sidecar (or use Aerospike Cloud).
    2. ``pip install aerospike-vector-search``
    3. Pass the connection details via ``AerospikeConfig``.

    Example config::

        {
            "vector_store": {
                "provider": "aerospike",
                "config": {
                    "host": "localhost",
                    "port": 5000,
                    "namespace": "mem0",
                    "set_name": "memories",
                    "index_name": "mem0_index",
                    "embedding_model_dims": 1536,
                    "distance_metric": "COSINE"
                }
            }
        }
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5000,
        namespace: str = "mem0",
        set_name: str = "memories",
        index_name: str = "mem0_index",
        vector_field: str = "embedding",
        embedding_model_dims: int = 1536,
        distance_metric: str = "COSINE",
        username: Optional[str] = None,
        password: Optional[str] = None,
        use_tls: bool = False,
        tls_cafile: Optional[str] = None,
    ):
        """
        Initialize the Aerospike Vector Search store.

        Args:
            host: AVS service host.
            port: AVS service port (default 5000).
            namespace: Aerospike namespace.
            set_name: Aerospike set (table) name.
            index_name: Name of the HNSW vector index.
            vector_field: Bin name storing the embedding vector.
            embedding_model_dims: Embedding dimensionality.
            distance_metric: One of ``'COSINE'``, ``'SQUARED_EUCLIDEAN'``,
                ``'DOT_PRODUCT'``.
            username: Optional username for authentication.
            password: Optional password for authentication.
            use_tls: Enable TLS for the AVS connection.
            tls_cafile: Path to CA certificate file when ``use_tls=True``.
        """
        # Lazy import — allows tests to stub sys.modules before instantiation
        # without the module-level ImportError firing at collection time.
        try:
            import aerospike_vector_search as _avs
            from aerospike_vector_search import types as _avs_types
        except ImportError:
            raise ImportError(
                "The 'aerospike-vector-search' library is required. "
                "Please install it using 'pip install aerospike-vector-search'."
            )

        self._avs = _avs
        self._avs_types = _avs_types

        self.namespace = namespace
        self.set_name = set_name
        self.index_name = index_name
        self.vector_field = vector_field
        self.embedding_model_dims = embedding_model_dims
        self.distance_metric = distance_metric

        # Build AVS connection objects
        seed = _avs_types.HostPort(host=host, port=port)

        tls_config = None
        if use_tls:
            tls_config = _avs_types.TLSConfig(cafile=tls_cafile)

        credentials = None
        if username and password:
            credentials = _avs_types.Credentials(username=username, password=password)

        self.client = _avs.Client(
            seeds=seed,
            listener_name=None,
            is_loadbalancer=False,
            credentials=credentials,
            tls_config=tls_config,
        )

        # Ensure the vector index exists
        self.create_col(
            name=self.index_name,
            vector_size=self.embedding_model_dims,
            distance=self.distance_metric,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _metric_type(self, distance: str) -> Any:
        """Resolve a distance string to the AVS VectorDistanceMetric enum."""
        mapping = {
            "COSINE": self._avs_types.VectorDistanceMetric.COSINE,
            "SQUARED_EUCLIDEAN": self._avs_types.VectorDistanceMetric.SQUARED_EUCLIDEAN,
            "DOT_PRODUCT": self._avs_types.VectorDistanceMetric.DOT_PRODUCT,
        }
        metric = mapping.get(distance.upper())
        if metric is None:
            raise ValueError(
                f"Unsupported distance metric '{distance}'. "
                f"Choose from: {list(mapping.keys())}"
            )
        return metric

    def _score_from_distance(self, distance: float) -> float:
        """Convert an AVS distance value to a similarity score in [0, 1]."""
        metric = self.distance_metric.upper()
        if metric == "COSINE":
            # AVS returns cosine distance (0 = identical, 2 = opposite)
            return max(0.0, 1.0 - distance)
        elif metric == "SQUARED_EUCLIDEAN":
            return 1.0 / (1.0 + distance)
        else:
            # DOT_PRODUCT: higher raw value = more similar
            return float(distance)

    def _record_to_output(self, record: Any) -> OutputData:
        """Convert an AVS neighbour / get result object to OutputData."""
        key = record.key.key if hasattr(record.key, "key") else str(record.key)
        bins: dict = record.bins if hasattr(record, "bins") else {}
        raw_payload = bins.get(_PAYLOAD_BIN, "{}")
        try:
            payload = json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
        except (json.JSONDecodeError, TypeError):
            payload = {}
        distance = getattr(record, "distance", None)
        score = self._score_from_distance(distance) if distance is not None else None
        return OutputData(id=key, score=score, payload=payload)

    # ------------------------------------------------------------------
    # VectorStoreBase interface
    # ------------------------------------------------------------------

    def create_col(self, name: str, vector_size: int, distance: str = "COSINE"):
        """Create the HNSW vector index (idempotent — skips if it already exists)."""
        try:
            self.client.index_create(
                namespace=self.namespace,
                name=name,
                vector_field=self.vector_field,
                dimensions=vector_size,
                vector_distance_metric=self._metric_type(distance),
                sets=self.set_name,
            )
            logger.info(f"Created Aerospike vector index '{name}'.")
        except Exception as exc:
            if "already exists" in str(exc).lower() or "exists" in str(exc).lower():
                logger.debug(f"Aerospike index '{name}' already exists — skipping creation.")
            else:
                raise

    def insert(self, vectors: List[list], payloads: List[Dict] = None, ids: List[str] = None):
        """Upsert vectors with their payloads into Aerospike."""
        payloads = payloads or [{}] * len(vectors)
        ids = ids or [str(i) for i in range(len(vectors))]

        for vec, payload, key in zip(vectors, payloads, ids):
            bins = {
                self.vector_field: vec,
                _PAYLOAD_BIN: json.dumps(payload),
            }
            self.client.upsert(
                namespace=self.namespace,
                set_name=self.set_name,
                key=key,
                record_data=bins,
            )

    def search(
        self, query: str, vectors: List[float], top_k: int = 5, filters: Optional[Dict] = None
    ) -> List[OutputData]:
        """Search for the top-k nearest vectors to ``vectors``."""
        raw = self.client.vector_search(
            namespace=self.namespace,
            index_name=self.index_name,
            query=vectors,
            limit=top_k,
        )
        output = [self._record_to_output(r) for r in raw]

        # Client-side metadata filtering (AVS OSS does not yet expose
        # server-side pre-filters on arbitrary payload bins in all setups).
        if filters:
            output = [
                item
                for item in output
                if all(item.payload.get(k) == v for k, v in filters.items() if v is not None)
            ]

        return output

    def delete(self, vector_id: str):
        """Delete a record by its key."""
        self.client.delete(
            namespace=self.namespace,
            set_name=self.set_name,
            key=vector_id,
        )

    def update(self, vector_id: str, vector: Optional[List[float]] = None, payload: Optional[Dict] = None):
        """Update a record's vector and/or payload bins in-place (upsert semantics)."""
        bins: dict = {}
        if vector is not None:
            bins[self.vector_field] = vector
        if payload is not None:
            bins[_PAYLOAD_BIN] = json.dumps(payload)

        if bins:
            self.client.upsert(
                namespace=self.namespace,
                set_name=self.set_name,
                key=vector_id,
                record_data=bins,
            )

    def get(self, vector_id: str) -> Optional[OutputData]:
        """Retrieve a single record by its key. Returns None if not found."""
        try:
            record = self.client.get(
                namespace=self.namespace,
                set_name=self.set_name,
                key=vector_id,
            )
            if record is None:
                return None
            return self._record_to_output(record)
        except Exception as exc:
            if "not found" in str(exc).lower() or "key not found" in str(exc).lower():
                return None
            raise

    def list_cols(self) -> List[str]:
        """List all vector index names in the configured namespace."""
        indexes = self.client.index_list()
        return [idx.id.name for idx in indexes if idx.id.namespace == self.namespace]

    def delete_col(self):
        """Drop the vector index. Records stored in the set are NOT deleted."""
        try:
            self.client.index_drop(namespace=self.namespace, name=self.index_name)
        except Exception as exc:
            logger.warning(f"Could not drop Aerospike index '{self.index_name}': {exc}")

    def col_info(self) -> Dict:
        """Return metadata about the current vector index."""
        try:
            return self.client.index_get(namespace=self.namespace, name=self.index_name)
        except Exception:
            return {}

    def list(self, filters: Optional[Dict] = None, top_k: int = 100) -> List[List[OutputData]]:
        """
        List stored memories.

        Performs a vector search with a zero vector to retrieve up to ``top_k``
        records, then applies ``filters`` (user_id, agent_id, run_id) client-side.
        """
        zero_vector = [0.0] * self.embedding_model_dims
        raw = self.client.vector_search(
            namespace=self.namespace,
            index_name=self.index_name,
            query=zero_vector,
            limit=top_k,
        )
        results = [self._record_to_output(r) for r in raw]

        if filters:
            results = [
                item
                for item in results
                if all(item.payload.get(k) == v for k, v in filters.items() if v is not None)
            ]

        return [results]

    def reset(self):
        """Drop and recreate the vector index (underlying records are preserved)."""
        logger.warning(f"Resetting Aerospike index '{self.index_name}'...")
        self.delete_col()
        self.create_col(
            name=self.index_name,
            vector_size=self.embedding_model_dims,
            distance=self.distance_metric,
        )
