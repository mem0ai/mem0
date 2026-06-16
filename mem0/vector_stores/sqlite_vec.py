import json
import logging
import os
import sqlite3
import struct
import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel

try:
    import sqlite_vec
except ImportError:
    raise ImportError(
        "Could not import sqlite_vec package. "
        "Please install it with `pip install sqlite-vec`."
    )

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # similarity score
    payload: Optional[Dict]  # metadata


class SQLiteVec(VectorStoreBase):
    """Vector store backed by sqlite-vec, using a single vec0 virtual table.

    The vec0 table uses regular (non-auxiliary) columns that support filtering
    directly during KNN search, guaranteeing exactly *top_k* results after
    metadata filtering.

    Two storage modes via the ``inline_payload`` flag:

    - ``inline_payload=True`` (default): Payload is stored as a TEXT column in
      the vec0 table. Filters are applied via ``json_extract`` in the KNN query.
      Best for small-to-medium payloads.

    - ``inline_payload=False``: Payload is stored in a separate metadata table.
      Filters are applied after KNN via a two-step lookup. Best for large
      payloads where storing text in the vector index would hurt performance.
    """

    VECTOR_TABLE = "mem0_vectors"
    METADATA_TABLE = "mem0_metadata"

    def __init__(
        self,
        collection_name: str,
        path: Optional[str] = None,
        embedding_model_dims: int = 1536,
        inline_payload: bool = True,
    ):
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.inline_payload = inline_payload
        self.path = path or f"/tmp/sqlite_vec/{collection_name}"

        db_dir = os.path.dirname(self.path) if os.path.dirname(self.path) else self.path
        os.makedirs(db_dir, exist_ok=True)

        db_path = f"{self.path}.db" if not self.path.endswith(".db") else self.path
        self._db_path = db_path

        self._conn = sqlite3.connect(db_path)
        self._conn.enable_load_extension(True)
        sqlite_vec.load(self._conn)
        self._conn.enable_load_extension(False)

        self._create_tables()

    # ------------------------------------------------------------------
    #  Schema
    # ------------------------------------------------------------------

    def _create_tables(self):
        """Create the vec0 virtual table and optional metadata table."""
        if self.inline_payload:
            self._conn.execute(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS {self.VECTOR_TABLE}
                USING vec0(
                    id TEXT,
                    embedding float[{self.embedding_model_dims}],
                    user_id TEXT,
                    agent_id TEXT,
                    run_id TEXT,
                    payload TEXT
                )
                """
            )
        else:
            self._conn.execute(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS {self.VECTOR_TABLE}
                USING vec0(
                    id TEXT,
                    embedding float[{self.embedding_model_dims}],
                    user_id TEXT,
                    agent_id TEXT,
                    run_id TEXT
                )
                """
            )
            self._conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.METADATA_TABLE} (
                    id TEXT PRIMARY KEY,
                    payload TEXT
                )
                """
            )
        self._conn.commit()

    # ------------------------------------------------------------------
    #  Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_vector(vector: List[float]) -> bytes:
        return struct.pack("%sf" % len(vector), *vector)

    @staticmethod
    def _serialize_payload(payload: Dict) -> str:
        return json.dumps(payload)

    @staticmethod
    def _deserialize_payload(payload_str: str) -> Dict:
        return json.loads(payload_str) if payload_str else {}

    # ------------------------------------------------------------------
    #  Filter helpers
    # ------------------------------------------------------------------

    def _build_filter_clause(self, filters: Optional[Dict]) -> tuple:
        """Build a SQL WHERE fragment and params from a filters dict.

        References the ``payload`` column via ``json_extract`` for payload-level
        filters, and uses direct column references for entity-level keys
        (user_id, agent_id, run_id) that are materialized as vec0 columns.
        """
        if not filters:
            return "", []

        conditions = []
        params = []
        entity_keys = {"user_id", "agent_id", "run_id"}

        for key, value in filters.items():
            if key in entity_keys:
                col = key
                if value is None:
                    conditions.append(f"{col} IS NULL")
                elif isinstance(value, list):
                    placeholders = ", ".join(["?" for _ in value])
                    conditions.append(f"{col} IN ({placeholders})")
                    params.extend(value)
                else:
                    conditions.append(f"{col} = ?")
                    params.append(value)
            else:
                if value is None:
                    conditions.append(f"json_extract(payload, '$.{key}') IS NULL")
                elif isinstance(value, list):
                    placeholders = ", ".join(["?" for _ in value])
                    conditions.append(f"json_extract(payload, '$.{key}') IN ({placeholders})")
                    params.extend(value)
                else:
                    conditions.append(f"json_extract(payload, '$.{key}') = ?")
                    params.append(value)

        if conditions:
            return " AND " + " AND ".join(conditions), params
        return "", []

    def _build_metadata_filter_clause(self, filters: Optional[Dict]) -> tuple:
        """Build a SQL WHERE fragment using json_extract for all keys.

        Used when querying the metadata table (which only has id + payload columns).
        """
        if not filters:
            return "", []

        conditions = []
        params = []

        for key, value in filters.items():
            if value is None:
                conditions.append(f"json_extract(payload, '$.{key}') IS NULL")
            elif isinstance(value, list):
                placeholders = ", ".join(["?" for _ in value])
                conditions.append(f"json_extract(payload, '$.{key}') IN ({placeholders})")
                params.extend(value)
            else:
                conditions.append(f"json_extract(payload, '$.{key}') = ?")
                params.append(value)

        if conditions:
            return " AND " + " AND ".join(conditions), params
        return "", []

    def create_col(self, name: str, vector_size: int = None, distance: str = None):
        self.collection_name = name
        self._create_tables()
        return self

    def insert(
        self,
        vectors: List[list],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
    ):
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]
        if payloads is None:
            payloads = [{} for _ in range(len(vectors))]
        if len(vectors) != len(ids) or len(vectors) != len(payloads):
            raise ValueError("Vectors, payloads, and IDs must have the same length")

        cursor = self._conn.cursor()
        for vector, vector_id, payload in zip(vectors, ids, payloads):
            vector_blob = self._serialize_vector(vector)
            uid = payload.get("user_id") or ""
            aid = payload.get("agent_id") or ""
            rid = payload.get("run_id") or ""
            payload_json = self._serialize_payload(payload)

            if self.inline_payload:
                cursor.execute(
                    f"INSERT INTO {self.VECTOR_TABLE}(id, embedding, user_id, agent_id, run_id, payload) "
                    f"VALUES (?, ?, ?, ?, ?, ?)",
                    (vector_id, vector_blob, uid, aid, rid, payload_json),
                )
            else:
                cursor.execute(
                    f"INSERT INTO {self.VECTOR_TABLE}(id, embedding, user_id, agent_id, run_id) "
                    f"VALUES (?, ?, ?, ?, ?)",
                    (vector_id, vector_blob, uid, aid, rid),
                )
                cursor.execute(
                    f"INSERT OR REPLACE INTO {self.METADATA_TABLE}(id, payload) VALUES (?, ?)",
                    (vector_id, payload_json),
                )

        self._conn.commit()
        logger.info(f"Inserted {len(vectors)} vectors into collection {self.collection_name}")

    def search(
        self, query: str, vectors: List[list], top_k: int = 5, filters: Optional[Dict] = None
    ) -> List[OutputData]:
        """Search for similar vectors.

        When ``inline_payload=True``, filters are applied directly in the KNN
        query via SQL WHERE, guaranteeing exactly *top_k* results (when
        available). When ``inline_payload=False``, a two-step approach is used.
        """
        query_vector = vectors[0] if isinstance(vectors[0], list) else vectors
        vector_blob = self._serialize_vector(query_vector)
        cursor = self._conn.cursor()

        filter_clause, filter_params = self._build_filter_clause(filters)

        if self.inline_payload:
            # Single-step: filter directly in the KNN query, guaranteed k results.
            query_sql = f"""
                SELECT id, distance, payload
                FROM {self.VECTOR_TABLE}
                WHERE embedding MATCH ? AND k = ?{filter_clause}
                ORDER BY distance
            """
            params = [vector_blob, top_k] + filter_params
            cursor.execute(query_sql, params)
            rows = cursor.fetchall()
        else:
            # Two-step: split filters into entity-level (on vec0) and payload-level (on metadata).
            entity_filters = {}
            payload_filters = {}
            entity_keys = {"user_id", "agent_id", "run_id"}
            if filters:
                for k, v in filters.items():
                    if k in entity_keys:
                        entity_filters[k] = v
                    else:
                        payload_filters[k] = v

            entity_clause, entity_params = self._build_filter_clause(entity_filters)
            fetch_k = top_k * 2

            cursor.execute(
                f"""
                SELECT id, distance
                FROM {self.VECTOR_TABLE}
                WHERE embedding MATCH ? AND k = ?{entity_clause}
                ORDER BY distance
                """,
                (vector_blob, fetch_k, *entity_params) if entity_params else (vector_blob, fetch_k),
            )
            knn_rows = cursor.fetchall()

            if not knn_rows:
                return []

            knn_ids = [row[0] for row in knn_rows]
            distance_map = {row[0]: row[1] for row in knn_rows}
            placeholders = ", ".join(["?" for _ in knn_ids])

            payload_clause, payload_params = self._build_filter_clause(payload_filters)
            if payload_clause:
                rows = cursor.execute(
                    f"SELECT id, payload FROM {self.METADATA_TABLE} "
                    f"WHERE id IN ({placeholders}){payload_clause}",
                    knn_ids + payload_params,
                ).fetchall()
            else:
                rows = cursor.execute(
                    f"SELECT id, payload FROM {self.METADATA_TABLE} WHERE id IN ({placeholders})",
                    knn_ids,
                ).fetchall()

            # Attach distances: (id, distance, payload)
            rows = [(r[0], distance_map.get(r[0]), r[1]) for r in rows]

        results = []
        for row in rows:
            vector_id, distance, payload_str = row
            if distance is None:
                continue
            payload = self._deserialize_payload(payload_str)
            # sqlite-vec vec0 uses L2 distance on normalized vectors.
            # L2² = 2 - 2*cos(θ), so cos(θ) = 1 - L2²/2.
            score = max(0.0, 1.0 - (float(distance) ** 2) / 2.0)
            results.append(OutputData(id=vector_id, score=score, payload=payload))

        return results[:top_k]

    def search_batch(
        self, queries: list, vectors_list: list, top_k: int = 1, filters: dict = None
    ) -> List[List[OutputData]]:
        """Batch search for multiple queries at once."""
        return [self.search(q, v, top_k=top_k, filters=filters) for q, v in zip(queries, vectors_list)]

    def delete(self, vector_id: str):
        cursor = self._conn.cursor()
        cursor.execute(f"DELETE FROM {self.VECTOR_TABLE} WHERE id = ?", (vector_id,))
        if not self.inline_payload:
            cursor.execute(f"DELETE FROM {self.METADATA_TABLE} WHERE id = ?", (vector_id,))
        self._conn.commit()
        logger.info(f"Deleted vector {vector_id} from collection {self.collection_name}")

    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None,
    ):
        cursor = self._conn.cursor()

        if self.inline_payload:
            cursor.execute(
                f"SELECT payload, user_id, agent_id, run_id FROM {self.VECTOR_TABLE} WHERE id = ?",
                (vector_id,),
            )
        else:
            cursor.execute(
                f"SELECT m.payload, v.user_id, v.agent_id, v.run_id FROM {self.VECTOR_TABLE} v "
                f"LEFT JOIN {self.METADATA_TABLE} m ON v.id = m.id WHERE v.id = ?",
                (vector_id,),
            )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Vector {vector_id} not found")

        current_payload = self._deserialize_payload(row[0] or "{}")
        user_id = row[1] or ""
        agent_id = row[2] or ""
        run_id = row[3] or ""

        if payload is not None:
            current_payload = payload.copy()
            user_id = current_payload.get("user_id", user_id)
            agent_id = current_payload.get("agent_id", agent_id)
            run_id = current_payload.get("run_id", run_id)

        if vector is None:
            raise ValueError(
                "Vector must be provided for update; vec0 does not expose the embedding column for reading."
            )

        # Delete old row and re-insert (vec0 does not support UPDATE on embedding)
        cursor.execute(f"DELETE FROM {self.VECTOR_TABLE} WHERE id = ?", (vector_id,))
        vector_blob = self._serialize_vector(vector)

        if self.inline_payload:
            cursor.execute(
                f"INSERT INTO {self.VECTOR_TABLE}(id, embedding, user_id, agent_id, run_id, payload) "
                f"VALUES (?, ?, ?, ?, ?, ?)",
                (vector_id, vector_blob, user_id, agent_id, run_id, self._serialize_payload(current_payload)),
            )
        else:
            cursor.execute(
                f"INSERT INTO {self.VECTOR_TABLE}(id, embedding, user_id, agent_id, run_id) "
                f"VALUES (?, ?, ?, ?, ?)",
                (vector_id, vector_blob, user_id, agent_id, run_id),
            )
            cursor.execute(
                f"UPDATE {self.METADATA_TABLE} SET payload = ? WHERE id = ?",
                (self._serialize_payload(current_payload), vector_id),
            )

        self._conn.commit()
        logger.info(f"Updated vector {vector_id} in collection {self.collection_name}")

    def get(self, vector_id: str) -> Optional[OutputData]:
        cursor = self._conn.cursor()
        if self.inline_payload:
            cursor.execute(
                f"SELECT payload FROM {self.VECTOR_TABLE} WHERE id = ?",
                (vector_id,),
            )
        else:
            cursor.execute(
                f"SELECT payload FROM {self.METADATA_TABLE} WHERE id = ?",
                (vector_id,),
            )
        row = cursor.fetchone()
        if row is None:
            return None
        return OutputData(id=vector_id, score=None, payload=self._deserialize_payload(row[0]))

    def list_cols(self) -> List[str]:
        db_dir = os.path.dirname(self._db_path)
        if not os.path.exists(db_dir):
            return [self.collection_name]
        collections = []
        for f in os.listdir(db_dir):
            if f.endswith(".db"):
                collections.append(f[:-3])
        return collections if collections else [self.collection_name]

    def delete_col(self):
        self._conn.close()
        try:
            if os.path.exists(self._db_path):
                os.remove(self._db_path)
            logger.info(f"Deleted collection {self.collection_name}")
        except Exception as e:
            logger.warning(f"Failed to delete collection file: {e}")

    def col_info(self) -> Dict:
        cursor = self._conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {self.VECTOR_TABLE}")
        count = cursor.fetchone()[0]
        return {
            "name": self.collection_name,
            "count": count,
            "dimension": self.embedding_model_dims,
            "distance": "cosine",
        }

    def list(self, filters: Optional[Dict] = None, top_k: int = 100) -> List[List[OutputData]]:
        cursor = self._conn.cursor()

        if self.inline_payload:
            filter_clause, filter_params = self._build_filter_clause(filters)
            if filter_clause:
                query_sql = f"""
                    SELECT id, payload FROM {self.VECTOR_TABLE}
                    WHERE 1=1 {filter_clause}
                    LIMIT ?
                """
            else:
                query_sql = f"SELECT id, payload FROM {self.VECTOR_TABLE} LIMIT ?"
            params = filter_params + [top_k]
        else:
            # Metadata table only has (id, payload) — all filters go through json_extract.
            filter_clause, filter_params = self._build_metadata_filter_clause(filters)
            if filter_clause:
                query_sql = f"""
                    SELECT id, payload FROM {self.METADATA_TABLE}
                    WHERE 1=1 {filter_clause}
                    LIMIT ?
                """
                params = filter_params + [top_k]
            else:
                query_sql = f"SELECT id, payload FROM {self.METADATA_TABLE} LIMIT ?"
                params = [top_k]

        cursor.execute(query_sql, params)
        rows = cursor.fetchall()

        results = []
        for row in rows:
            vector_id, payload_str = row
            results.append(OutputData(id=vector_id, score=None, payload=self._deserialize_payload(payload_str)))

        return [results]

    def reset(self):
        logger.warning(f"Resetting collection {self.collection_name}...")
        self.delete_col()
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._conn = sqlite3.connect(self._db_path)
        self._conn.enable_load_extension(True)
        sqlite_vec.load(self._conn)
        self._conn.enable_load_extension(False)
        self._create_tables()