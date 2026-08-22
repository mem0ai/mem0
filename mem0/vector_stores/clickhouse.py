import json
import logging
from typing import Dict, List, Optional
import uuid

try:
    import clickhouse_connect
except ImportError:
    raise ImportError(
        "The 'clickhouse-connect' library is required. Please install it using 'pip install clickhouse-connect'."
    )

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[Dict]


class ClickhouseDB(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        host: str = "localhost",
        port: int = 8123,
        username: str = "default",
        password: str = "",
        local: bool = False,
        **kwargs,
    ):
        self.collection_name = collection_name
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.local = local
        self.kwargs = kwargs

        try:
            self.client = clickhouse_connect.get_client(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                **self.kwargs,
            )
        except Exception as e:
            logger.error(f"Failed to connect to ClickHouse: {e}")
            raise e

        # Don't create table on init unless requested or wait till insert?
        # Actually create_col is called explicitly or we can ensure it's created on first insert.
        # VectorStoreBase providers usually create on init.
        self.create_col(self.collection_name)

    def create_col(self, name: str, vector_size: int = None, distance: str = None):
        """Create a new table/collection."""
        query = f"""
            CREATE TABLE IF NOT EXISTS {name} (
                id String,
                vector Array(Float32),
                payload String
            ) ENGINE = MergeTree()
            ORDER BY id
        """
        self.client.command(query)

    def insert(self, vectors: List[list], payloads: Optional[List[Dict]] = None, ids: Optional[List[str]] = None):
        """Insert vectors into the collection."""
        if not ids:
            ids = [str(uuid.uuid4()) for _ in vectors]

        if not payloads:
            payloads = [{} for _ in vectors]

        payload_strs = [json.dumps(p) for p in payloads]

        data = [[ids[i], vectors[i], payload_strs[i]] for i in range(len(vectors))]

        self.client.insert(
            self.collection_name,
            data,
            column_names=["id", "vector", "payload"],
        )

    def search(
        self, query: str, vectors: List[list], top_k: int = 5, filters: Optional[Dict] = None
    ) -> List[OutputData]:
        """Search for similar vectors."""
        # Using the first vector as query
        vector = vectors[0]

        where_clause = ""
        if filters:
            conditions = self._parse_filters(filters)
            if conditions:
                where_clause = f"WHERE {conditions}"

        # We use cosineDistance. score = 1.0 - cosineDistance
        # clickhouse cosineDistance returns values in [0, 2], where 0 is identical, 2 is opposite.
        # So score = 1.0 - distance is appropriate.
        sql = f"""
            SELECT id, 
                   1.0 - cosineDistance(vector, {vector}) as score, 
                   payload
            FROM {self.collection_name}
            {where_clause}
            ORDER BY score DESC
            LIMIT {top_k}
        """

        result = self.client.query(sql)

        outputs = []
        for row in result.result_rows:
            outputs.append(
                OutputData(
                    id=row[0],
                    score=row[1],
                    payload=json.loads(row[2]) if row[2] else None,
                )
            )
        return outputs

    def delete(self, vector_id: str):
        """Delete a vector by ID."""
        sql = f"ALTER TABLE {self.collection_name} DELETE WHERE id = '{vector_id}'"
        self.client.command(sql)

    def update(self, vector_id: str, vector: Optional[List[float]] = None, payload: Optional[Dict] = None):
        """Update a vector and its payload. ClickHouse mutations are asynchronous."""
        if vector is not None:
            self.client.command(f"ALTER TABLE {self.collection_name} UPDATE vector = {vector} WHERE id = '{vector_id}'")

        if payload is not None:
            payload_str = json.dumps(payload).replace("'", "''")
            self.client.command(
                f"ALTER TABLE {self.collection_name} UPDATE payload = '{payload_str}' WHERE id = '{vector_id}'"
            )

    def get(self, vector_id: str) -> Optional[OutputData]:
        """Retrieve a vector by ID."""
        sql = f"SELECT id, vector, payload FROM {self.collection_name} WHERE id = '{vector_id}' LIMIT 1"
        result = self.client.query(sql)

        if not result.result_rows:
            return None

        row = result.result_rows[0]
        return OutputData(
            id=row[0],
            score=None,
            payload=json.loads(row[2]) if row[2] else None,
        )

    def list_cols(self) -> List[str]:
        """List all tables."""
        result = self.client.query("SHOW TABLES")
        return [row[0] for row in result.result_rows]

    def delete_col(self):
        """Delete a collection."""
        self.client.command(f"DROP TABLE IF EXISTS {self.collection_name}")

    def col_info(self) -> Dict:
        """Get information about a collection."""
        sql = f"SELECT count() FROM {self.collection_name}"
        try:
            count = self.client.query(sql).result_rows[0][0]
            return {"name": self.collection_name, "count": count}
        except Exception:
            return {"name": self.collection_name, "count": 0}

    def list(self, filters: Optional[Dict] = None, top_k: int = 100) -> List[OutputData]:
        """List all memories."""
        where_clause = ""
        if filters:
            conditions = self._parse_filters(filters)
            if conditions:
                where_clause = f"WHERE {conditions}"

        sql = f"SELECT id, payload FROM {self.collection_name} {where_clause} LIMIT {top_k}"
        result = self.client.query(sql)

        outputs = []
        for row in result.result_rows:
            outputs.append(
                OutputData(
                    id=row[0],
                    score=None,
                    payload=json.loads(row[1]) if row[1] else None,
                )
            )
        return outputs

    def reset(self):
        """Reset the index."""
        self.delete_col()
        self.create_col(self.collection_name)

    def _parse_filters(self, filters: Dict) -> str:
        """Convert filters dict to ClickHouse JSON extract SQL WHERE clause."""
        conditions = []
        for key, value in filters.items():
            if isinstance(value, dict):
                # Handle operators like $eq, $ne etc. if needed, but for simplicity assuming exact match
                pass
            else:
                # Basic exact match on payload fields
                # ClickHouse JSON extraction: JSONExtractString(payload, 'key') = 'value'
                if isinstance(value, str):
                    val = value.replace("'", "''")
                    conditions.append(f"JSONExtractString(payload, '{key}') = '{val}'")
                elif isinstance(value, int) or isinstance(value, float):
                    conditions.append(f"JSONExtractFloat(payload, '{key}') = {value}")
                elif isinstance(value, bool):
                    val = 1 if value else 0
                    conditions.append(f"JSONExtractBool(payload, '{key}') = {val}")

        return " AND ".join(conditions) if conditions else ""
