import json
import logging
from typing import Any, Dict, List, Optional
import uuid

try:
    # pyrefly: ignore [missing-import]
    import clickhouse_connect
except ImportError:
    clickhouse_connect = None

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class ClickhouseDB(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        embedding_model_dims: int,
        host: str = "localhost",
        port: int = 8123,
        username: str = "default",
        password: str = "",
        database: str = "default",
        secure: bool = False,
        client: Optional[Any] = None,
        **kwargs,
    ):
        if clickhouse_connect is None:
            raise ImportError(
                "ClickHouse requires the clickhouse-connect library. "
                "Install it with: pip install clickhouse-connect"
            )

        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims

        if client:
            self.client = client
        else:
            self.client = clickhouse_connect.get_client(
                host=host,
                port=port,
                username=username,
                password=password,
                database=database,
                secure=secure,
                **kwargs,
            )
            
        self.create_col()

    def create_col(self, *args, **kwargs):
        """Create the collection table if it doesn't exist."""
        # Using ReplacingMergeTree so that re-inserts with the same id will eventually replace the old row,
        # which makes updates easier.
        query = f"""
            CREATE TABLE IF NOT EXISTS {self.collection_name} (
                id String,
                payload String,
                vector Array(Float32)
            ) ENGINE = ReplacingMergeTree()
            ORDER BY id
        """
        self.client.command(query)

    def insert(self, vectors: List[List[float]], payloads: Optional[List[Dict]] = None, ids: Optional[List[str]] = None):
        """Insert vectors into the collection."""
        if not ids:
            ids = [str(uuid.uuid4()) for _ in vectors]
        if not payloads:
            payloads = [{} for _ in vectors]

        # Ensure we have matching lengths
        if len(vectors) != len(ids) or len(vectors) != len(payloads):
            raise ValueError("Length of vectors, ids, and payloads must match.")

        # Serialize payloads to JSON strings
        serialized_payloads = [json.dumps(p) for p in payloads]

        data = list(zip(ids, serialized_payloads, vectors))
        self.client.insert(
            self.collection_name, 
            data, 
            column_names=["id", "payload", "vector"]
        )
        return ids

    def search(self, query: List[float], top_k: int = 5, filters: Optional[Dict] = None, **kwargs):
        """Search for similar vectors using cosine distance."""
        # ClickHouse cosineDistance returns a distance where 0 is identical and larger values are less similar.
        # We want to return a similarity score where higher is better (range ~ [0, 1]).
        # cosineDistance = 1 - cosine_similarity. So similarity = 1 - distance.
        
        filter_clause = ""
        # Extremely basic JSON filter handling for ClickHouse JSON string.
        # For production use, it's better to extract keys into columns or use ClickHouse's JSON extract functions.
        if filters:
            conditions = []
            for k, v in filters.items():
                # using JSONExtractString or JSONExtract
                conditions.append(f"JSONExtractString(payload, '{k}') = '{v}'")
            filter_clause = "WHERE " + " AND ".join(conditions)

        sql = f"""
            SELECT 
                id, 
                payload, 
                1 - cosineDistance(vector, {query}) as score
            FROM {self.collection_name}
            {filter_clause}
            ORDER BY score DESC
            LIMIT {top_k}
        """
        
        result = self.client.query(sql)
        
        hits = []
        for row in result.result_rows:
            hit = {
                "id": row[0],
                "payload": json.loads(row[1]) if row[1] else {},
                "score": float(row[2])
            }
            hits.append(hit)
            
        return hits

    def delete(self, vector_id: str):
        """Delete a vector by ID. Uses mutation which is async in ClickHouse."""
        query = f"ALTER TABLE {self.collection_name} DELETE WHERE id = '{vector_id}'"
        self.client.command(query)

    def update(self, vector_id: str, vector: Optional[List[float]] = None, payload: Optional[Dict] = None):
        """Update a vector and its payload."""
        # ClickHouse mutations are heavy. A lighter way for ReplacingMergeTree is to insert a new row with the same ID.
        # We first need to get the existing row to fill in missing parts.
        existing = self.get(vector_id)
        if not existing:
            raise ValueError(f"Vector with id {vector_id} not found")

        updated_vector = vector if vector is not None else existing.vector
        updated_payload = payload if payload is not None else existing.payload

        self.insert([updated_vector], [updated_payload], [vector_id])
        # To force replace immediately (optional but good for consistency in tests):
        self.client.command(f"OPTIMIZE TABLE {self.collection_name} FINAL")

    def get(self, vector_id: str):
        """Retrieve a vector by ID."""
        sql = f"SELECT id, payload, vector FROM {self.collection_name} WHERE id = '{vector_id}' LIMIT 1"
        result = self.client.query(sql)
        
        if not result.result_rows:
            return None
            
        row = result.result_rows[0]
        
        class VectorResult:
            def __init__(self, id, payload, vector):
                self.id = id
                self.payload = payload
                self.vector = vector
                
        return VectorResult(
            id=row[0],
            payload=json.loads(row[1]) if row[1] else {},
            vector=row[2]
        )

    def list_cols(self) -> List[str]:
        """List all collections/tables."""
        result = self.client.query("SHOW TABLES")
        return [row[0] for row in result.result_rows]

    def delete_col(self):
        """Delete the collection."""
        self.client.command(f"DROP TABLE IF EXISTS {self.collection_name}")

    def col_info(self) -> Dict:
        """Get information about the collection."""
        result = self.client.query(f"SELECT count() FROM {self.collection_name}")
        count = result.result_rows[0][0] if result.result_rows else 0
        return {"name": self.collection_name, "count": count}

    def list(self, filters: Optional[Dict] = None, top_k: Optional[int] = None) -> List[Dict]:
        """List all memories (vectors) in the collection."""
        filter_clause = ""
        if filters:
            conditions = []
            for k, v in filters.items():
                conditions.append(f"JSONExtractString(payload, '{k}') = '{v}'")
            filter_clause = "WHERE " + " AND ".join(conditions)
            
        limit_clause = f"LIMIT {top_k}" if top_k else ""
        
        sql = f"""
            SELECT id, payload, vector
            FROM {self.collection_name}
            {filter_clause}
            {limit_clause}
        """
        result = self.client.query(sql)
        
        memories = []
        for row in result.result_rows:
            memories.append({
                "id": row[0],
                "payload": json.loads(row[1]) if row[1] else {},
                "vector": row[2]
            })
        return memories

    def reset(self):
        """Reset the collection by dropping and recreating it."""
        self.delete_col()
        self.create_col()
