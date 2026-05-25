import json
import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

try:
    import singlestoredb as s2
except ImportError:
    raise ImportError("The 'singlestoredb' package is required. Install it with: pip install singlestoredb")

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class SingleStore(VectorStoreBase):
    def __init__(
        self,
        host,
        port,
        user,
        password,
        database,
        collection_name,
        embedding_model_dims,
        connection_url=None,
        pool_size=5,
        use_vector_index=True,
        use_fulltext_index=True,
        distance_strategy="DOT_PRODUCT",
    ):
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.use_vector_index = use_vector_index
        self.use_fulltext_index = use_fulltext_index
        self.distance_strategy = distance_strategy

        if connection_url:
            self.conn_params = {"host": connection_url}
        else:
            self.conn_params = {
                "host": host,
                "port": port,
                "user": user,
                "password": password,
                "database": database,
            }

        self.pool = s2.connect(**self.conn_params)

        collections = self.list_cols()
        if collection_name not in collections:
            self.create_col()

    def _get_connection(self):
        """Get a database connection, reconnecting if needed."""
        if not self.pool.is_connected():
            self.pool = s2.connect(**self.conn_params)
        return self.pool

    def _build_filter_clause(self, filters: Optional[Dict] = None, prefix="WHERE"):
        """Build WHERE/AND clause from filters dict. Returns (clause_str, params_list)."""
        if not filters:
            return "", []

        conditions = []
        params = []
        for k, v in filters.items():
            if k in ("$or", "$not"):
                continue
            conditions.append("JSON_EXTRACT_STRING(payload, %s) = %s")
            params.extend([k, str(v)])

        if not conditions:
            return "", []
        clause = f"{prefix} " + " AND ".join(conditions)
        return clause, params

    def create_col(self, name=None, vector_size=None, distance=None) -> None:
        conn = self._get_connection()
        cur = conn.cursor()
        dims = vector_size or self.embedding_model_dims

        # Vector indexes require columnstore (default) and VECTOR type
        vector_index_sql = ""
        if self.use_vector_index:
            index_options = json.dumps({"metric_type": self.distance_strategy, "index_type": "HNSW_FLAT"})
            vector_index_sql = f",\n            VECTOR INDEX vec_idx (vector) INDEX_OPTIONS '{index_options}'"

        fulltext_index_sql = ""
        if self.use_fulltext_index:
            fulltext_index_sql = ",\n            FULLTEXT INDEX ft_idx (text_lemmatized)"

        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS `{self.collection_name}` (
                id VARCHAR(64) NOT NULL,
                vector VECTOR({dims}, F32) NOT NULL,
                payload JSON,
                text_lemmatized TEXT,
                SHARD KEY (id),
                KEY (id) USING HASH{vector_index_sql}{fulltext_index_sql}
            )
        """)
        conn.commit()
        cur.close()

    def insert(self, vectors: List[List[float]], payloads=None, ids=None) -> None:
        logger.info(f"Inserting {len(vectors)} vectors into {self.collection_name}")
        conn = self._get_connection()
        cur = conn.cursor()

        # Batch insert for performance
        data = []
        for id_, vector, payload in zip(ids, vectors, payloads):
            text_lemmatized = payload.get("text_lemmatized", "") if payload else ""
            data.append((id_, json.dumps(vector), json.dumps(payload), text_lemmatized))

        cur.executemany(
            f"INSERT INTO `{self.collection_name}` (id, vector, payload, text_lemmatized) "
            f"VALUES (%s, %s :> VECTOR({self.embedding_model_dims}, F32), %s, %s)",
            data,
        )
        conn.commit()
        cur.close()

    def search(
        self,
        query: str,
        vectors: List[float],
        top_k: Optional[int] = 5,
        filters: Optional[Dict] = None,
    ) -> List[OutputData]:
        conn = self._get_connection()
        cur = conn.cursor()

        filter_clause, filter_params = self._build_filter_clause(filters)
        order_dir = "DESC" if self.distance_strategy == "DOT_PRODUCT" else "ASC"

        sql = f"""
            SELECT id, {self.distance_strategy}(vector, %s :> VECTOR({self.embedding_model_dims}, F32)) AS score, payload
            FROM `{self.collection_name}`
            {filter_clause}
            ORDER BY score {order_dir}
            LIMIT %s
        """
        params = [json.dumps(vectors)] + filter_params + [top_k]
        cur.execute(sql, params)
        results = cur.fetchall()
        cur.close()

        return [
            OutputData(
                id=str(r[0]),
                score=float(r[1]),
                payload=json.loads(r[2]) if isinstance(r[2], str) else r[2],
            )
            for r in results
        ]

    def keyword_search(self, query: str, top_k: int = 5, filters: Optional[Dict] = None):
        if not self.use_fulltext_index:
            return None

        conn = self._get_connection()
        cur = conn.cursor()

        filter_clause, filter_params = self._build_filter_clause(filters, prefix="AND")

        sql = f"""
            SELECT id, MATCH(text_lemmatized) AGAINST(%s) AS score, payload
            FROM `{self.collection_name}`
            WHERE MATCH(text_lemmatized) AGAINST(%s)
            {filter_clause}
            ORDER BY score DESC
            LIMIT %s
        """
        params = [query, query] + filter_params + [top_k]

        try:
            cur.execute(sql, params)
            results = cur.fetchall()
            cur.close()
            return [
                OutputData(
                    id=str(r[0]),
                    score=float(r[1]),
                    payload=json.loads(r[2]) if isinstance(r[2], str) else r[2],
                )
                for r in results
            ]
        except Exception as e:
            logger.debug(f"Keyword search failed: {e}")
            cur.close()
            return None

    def delete(self, vector_id: str) -> None:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute(f"DELETE FROM `{self.collection_name}` WHERE id = %s", (vector_id,))
        conn.commit()
        cur.close()

    def update(self, vector_id: str, vector: Optional[List[float]] = None, payload: Optional[Dict] = None) -> None:
        conn = self._get_connection()
        cur = conn.cursor()

        if vector:
            cur.execute(
                f"UPDATE `{self.collection_name}` SET vector = %s :> VECTOR({self.embedding_model_dims}, F32) WHERE id = %s",
                (json.dumps(vector), vector_id),
            )
        if payload:
            text_lemmatized = payload.get("text_lemmatized", "")
            cur.execute(
                f"UPDATE `{self.collection_name}` SET payload = %s, text_lemmatized = %s WHERE id = %s",
                (json.dumps(payload), text_lemmatized, vector_id),
            )

        conn.commit()
        cur.close()

    def get(self, vector_id: str) -> Optional[OutputData]:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, payload FROM `{self.collection_name}` WHERE id = %s",
            (vector_id,),
        )
        result = cur.fetchone()
        cur.close()

        if not result:
            return None
        payload = json.loads(result[1]) if isinstance(result[1], str) else result[1]
        return OutputData(id=str(result[0]), score=None, payload=payload)

    def list_cols(self) -> List[str]:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SHOW TABLES")
        tables = [row[0] for row in cur.fetchall()]
        cur.close()
        return tables

    def delete_col(self) -> None:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute(f"DROP TABLE IF EXISTS `{self.collection_name}`")
        conn.commit()
        cur.close()

    def col_info(self) -> Dict[str, Any]:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM `{self.collection_name}`")
        count = cur.fetchone()[0]
        cur.close()
        return {"name": self.collection_name, "count": count}

    def list(self, filters: Optional[Dict] = None, top_k: Optional[int] = 100) -> List[List[OutputData]]:
        conn = self._get_connection()
        cur = conn.cursor()

        filter_clause, filter_params = self._build_filter_clause(filters)

        sql = f"""
            SELECT id, payload FROM `{self.collection_name}`
            {filter_clause}
            LIMIT %s
        """
        params = filter_params + [top_k]
        cur.execute(sql, params)
        results = cur.fetchall()
        cur.close()

        return [[
            OutputData(
                id=str(r[0]),
                score=None,
                payload=json.loads(r[1]) if isinstance(r[1], str) else r[1],
            )
            for r in results
        ]]

    def reset(self) -> None:
        logger.warning(f"Resetting collection {self.collection_name}")
        self.delete_col()
        self.create_col()

    def __del__(self) -> None:
        try:
            if hasattr(self, "pool") and self.pool:
                self.pool.close()
        except Exception:
            pass
