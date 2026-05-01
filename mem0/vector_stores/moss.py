import asyncio
import concurrent.futures
import json
import logging
from typing import Dict, List, Optional

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: str
    score: float
    payload: Dict


def _run_sync(coro):
    """Run an async coroutine from synchronous code.

    Spawns a worker thread when called from inside a running event loop
    (e.g. FastAPI / Jupyter) so asyncio.run() doesn't raise RuntimeError.
    """
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


class MossVectorStore(VectorStoreBase):
    """mem0 vector store backed by Moss (https://moss.dev).

    Moss manages its own embeddings, so mem0's pre-computed embedding vectors
    are not forwarded to the index.  The ``query`` text passed to ``search()``
    is used directly for semantic / hybrid retrieval via the Moss SDK.

    Metadata constraints
    --------------------
    Moss metadata values must be strings (``Dict[str, str]``).  The full mem0
    payload is serialised to JSON and stored under the ``_payload`` metadata
    key so that all fields and types are round-tripped faithfully.

    Metadata filtering
    ------------------
    Moss metadata filters only work on a *locally loaded* index
    (``load_index()``).  This provider auto-loads the index the first time a
    filtered query is issued.  Set ``load_index_on_init=True`` in config to
    pre-load eagerly.
    """

    def __init__(
        self,
        collection_name: str,
        project_id: str,
        project_key: str,
        model_id: str = "moss-minilm",
        embedding_model_dims: Optional[int] = None,  # unused — Moss manages its own embeddings
        alpha: float = 0.8,
        load_index_on_init: bool = False,
    ):
        from moss import MossClient  # noqa: PLC0415

        self.client = MossClient(project_id, project_key)
        self.collection_name = collection_name
        self.model_id = model_id
        self.alpha = alpha
        self._index_created = False
        self._index_loaded = False

        self.create_col()
        if load_index_on_init:
            self._load_index()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_index(self):
        """Download the index into memory for fast local queries and filtering."""
        if self._index_loaded or not self._index_created:
            return
        try:
            _run_sync(self.client.load_index(self.collection_name))
            self._index_loaded = True
            logger.info(f"Moss index '{self.collection_name}' loaded into memory")
        except Exception as exc:
            logger.warning(f"Could not load Moss index '{self.collection_name}' into memory: {exc}")

    def _reload_index(self):
        """Force a reload after a mutation so in-memory data stays current."""
        if not self._index_loaded:
            return
        self._index_loaded = False
        self._load_index()

    def _payload_to_doc(self, vector_id: str, payload: dict):
        """Serialise a mem0 payload into a Moss DocumentInfo."""
        from moss import DocumentInfo  # noqa: PLC0415

        text = payload.get("data", "")

        # Moss metadata is Dict[str, str] — stringify every value and store
        # the original JSON blob so types survive a round-trip.
        meta: dict = {}
        for k, v in payload.items():
            if v is not None:
                meta[k] = str(v)
        meta["_payload"] = json.dumps(payload, default=str)

        return DocumentInfo(id=str(vector_id), text=text, metadata=meta)

    def _doc_to_output(self, doc, score: float = 0.0) -> OutputData:
        """Convert a Moss document to OutputData."""
        payload: dict = {}
        if doc.metadata:
            raw = doc.metadata.get("_payload")
            if raw:
                try:
                    payload = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    payload = {k: v for k, v in doc.metadata.items() if k != "_payload"}
            else:
                payload = dict(doc.metadata)
        return OutputData(id=doc.id, score=score, payload=payload)
\
    def create_col(self, _vector_size=None, _distance=None):
        """Verify the index exists; creation is deferred to the first insert."""
        indexes = _run_sync(self.client.list_indexes())
        for idx in indexes:
            if idx.name == self.collection_name:
                self._index_created = True
                logger.debug(f"Moss index '{self.collection_name}' already exists")
                return
        logger.debug(f"Moss index '{self.collection_name}' not found — will create on first insert")
        self._index_created = False

    def insert(self, vectors: list, payloads: list = None, ids: list = None):
        """Upsert documents into the Moss index.

        ``vectors`` are accepted for interface compatibility but not forwarded
        to Moss — Moss handles its own embeddings.
        """
        from moss import MutationOptions  # noqa: PLC0415

        docs = [
            self._payload_to_doc(
                str(ids[i]) if ids else str(i),
                payloads[i] if payloads else {},
            )
            for i in range(len(vectors))
        ]

        if not self._index_created:
            logger.info(f"Creating Moss index '{self.collection_name}' with {len(docs)} initial document(s)")
            _run_sync(self.client.create_index(self.collection_name, docs, self.model_id))
            self._index_created = True
        else:
            _run_sync(self.client.add_docs(self.collection_name, docs, MutationOptions(upsert=True)))

        self._reload_index()

    def search(self, query: str, vectors: list, top_k: int = 5, filters: dict = None) -> List[OutputData]:
        """Semantic / hybrid search.  ``vectors`` is ignored — Moss re-embeds ``query``."""
        from moss import QueryOptions  # noqa: PLC0415

        if not self._index_created:
            return []

        moss_filter = None
        if filters:
            self._load_index()  # filtering requires a locally loaded index
            moss_filter = self._convert_filters(filters)

        opts = QueryOptions(top_k=top_k, alpha=self.alpha, filter=moss_filter)
        result = _run_sync(self.client.query(self.collection_name, query, opts))
        return [self._doc_to_output(d, d.score) for d in result.docs]

    def delete(self, vector_id):
        """Delete a single document by ID."""
        _run_sync(self.client.delete_docs(self.collection_name, [str(vector_id)]))
        self._reload_index()

    def update(self, vector_id, vector=None, payload: dict = None):
        """Update a document's text / metadata.  ``vector`` is ignored."""
        if payload is None:
            return
        from moss import MutationOptions  # noqa: PLC0415

        doc = self._payload_to_doc(str(vector_id), payload)
        _run_sync(self.client.add_docs(self.collection_name, [doc], MutationOptions(upsert=True)))
        self._reload_index()

    def get(self, vector_id) -> Optional[OutputData]:
        """Retrieve a single document by ID."""
        from moss import GetDocumentsOptions  # noqa: PLC0415

        if not self._index_created:
            return None
        docs = _run_sync(
            self.client.get_docs(self.collection_name, GetDocumentsOptions(doc_ids=[str(vector_id)]))
        )
        return self._doc_to_output(docs[0]) if docs else None

    def list_cols(self):
        """Return a list of all Moss IndexInfo objects for this project."""
        return _run_sync(self.client.list_indexes())

    def delete_col(self):
        """Delete the Moss index and all its documents."""
        _run_sync(self.client.delete_index(self.collection_name))
        self._index_created = False
        self._index_loaded = False

    def col_info(self):
        """Return Moss IndexInfo for the current index."""
        return _run_sync(self.client.get_index(self.collection_name))

    def list(self, filters: dict = None, top_k: int = 100):
        """Return all documents, optionally filtered client-side.

        Returns a ``(results, None)`` tuple to match Qdrant's scroll convention.
        """
        if not self._index_created:
            return [], None

        docs = _run_sync(self.client.get_docs(self.collection_name))
        results = [self._doc_to_output(d) for d in docs]
        if filters:
            results = [r for r in results if self._match_payload(r.payload, filters)]
        return results[:top_k], None

    def reset(self):
        """Delete and clear the index.  Re-creation is deferred to the next insert."""
        logger.warning(f"Resetting Moss index '{self.collection_name}'")
        self.delete_col()


    def _convert_filters(self, filters: dict) -> Optional[dict]:
        """Translate mem0 filter dicts to Moss QueryOptions filter shape.

        mem0 logical keys: ``AND`` / ``OR`` / ``NOT`` (also ``$and`` / ``$or`` / ``$not``).
        Moss logical shape: ``{"$and": [...]}`` / ``{"$or": [...]}``.
        Moss field shape:   ``{"field": "user_id", "condition": {"$eq": "alice"}}``.

        NOTE: Moss does not support ``$not`` — NOT clauses are skipped.
        All metadata values are strings, so ``$gt``/``$lt`` comparisons are lexicographic.
        """
        if not filters:
            return None

        key_map = {"$and": "AND", "$or": "OR", "$not": "NOT"}
        normalized: dict = {}
        for k, v in filters.items():
            norm = key_map.get(k, k)
            if norm not in normalized:
                normalized[norm] = v

        conditions = []
        for key, value in normalized.items():
            if key == "AND":
                subs = [self._convert_filters(s) for s in value]
                subs = [s for s in subs if s is not None]
                if subs:
                    conditions.append({"$and": subs})
            elif key == "OR":
                subs = [self._convert_filters(s) for s in value]
                subs = [s for s in subs if s is not None]
                if subs:
                    conditions.append({"$or": subs})
            elif key == "NOT":
                logger.debug("Moss does not support $not metadata filters; skipping NOT clause")
            else:
                cond = self._convert_field_filter(key, value)
                if cond is not None:
                    conditions.append(cond)

        if not conditions:
            return None
        return conditions[0] if len(conditions) == 1 else {"$and": conditions}

    def _convert_field_filter(self, field: str, value) -> Optional[dict]:
        """Convert a single mem0 field condition to a Moss filter dict."""
        if value == "*":
            return None  # wildcard — match any, skip

        if isinstance(value, list):
            return {"field": field, "condition": {"$in": [str(v) for v in value]}}

        if not isinstance(value, dict):
            return {"field": field, "condition": {"$eq": str(value)}}

        op_map = {
            "eq": "$eq", "ne": "$ne",
            "gt": "$gt", "gte": "$gte",
            "lt": "$lt", "lte": "$lte",
            "in": "$in", "nin": "$nin",
        }
        cond: dict = {}
        for op, v in value.items():
            if op in op_map:
                if op in ("in", "nin"):
                    cond[op_map[op]] = [str(x) for x in v]
                elif op in ("eq", "ne"):
                    cond[op_map[op]] = str(v)
                else:
                    cond[op_map[op]] = v
            elif op in ("contains", "icontains"):
                logger.debug(f"Filter operator '{op}' not supported by Moss metadata filters; skipping field '{field}'")

        return {"field": field, "condition": cond} if cond else None

    def _match_payload(self, payload: dict, filters: dict) -> bool:
        """Evaluate a mem0 filter dict against a payload dict in Python."""
        for key, value in filters.items():
            if key in ("AND", "$and"):
                if not all(self._match_payload(payload, f) for f in value):
                    return False
            elif key in ("OR", "$or"):
                if not any(self._match_payload(payload, f) for f in value):
                    return False
            elif key in ("NOT", "$not"):
                if any(self._match_payload(payload, f) for f in value):
                    return False
            else:
                field_val = payload.get(key)
                if isinstance(value, dict):
                    for op, v in value.items():
                        op_norm = op.lstrip("$")
                        if op_norm == "eq" and field_val != v:
                            return False
                        elif op_norm == "ne" and field_val == v:
                            return False
                        elif op_norm == "in" and field_val not in v:
                            return False
                        elif op_norm == "nin" and field_val in v:
                            return False
                        elif op_norm == "gt" and not (field_val is not None and field_val > v):
                            return False
                        elif op_norm == "gte" and not (field_val is not None and field_val >= v):
                            return False
                        elif op_norm == "lt" and not (field_val is not None and field_val < v):
                            return False
                        elif op_norm == "lte" and not (field_val is not None and field_val <= v):
                            return False
                elif field_val != value:
                    return False
        return True
