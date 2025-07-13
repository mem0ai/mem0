import json
import logging
from typing import List, Optional

from pydantic import BaseModel

try:
    import pymysql
except ImportError:
    raise ImportError("The 'pymysql' library is required. Please install it using 'pip install pymysql'.")

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class TiDB(VectorStoreBase):
    def __init__(
        self,
        host,
        port,
        user,
        password,
        database,
        collection_name,
        embedding_model_dims,
    ):
        """
        Initialize the TiDB vector store.

        Args:
            host (str): Database host
            port (int): Database port
            user (str): Database user
            password (str): Database password
            database (str): Database name
            collection_name (str): Collection name
            embedding_model_dims (int): Dimension of the embedding vector
        """
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims

        self.conn = pymysql.connect(host=host, port=port, user=user, password=password, database=database)
        self.cur = self.conn.cursor()

        collections = self.list_cols()
        if collection_name not in collections:
            self.create_col(embedding_model_dims)

    def create_col(self, vector_size):
        """
        Create a new collection (table in TiDB).

        Args:
            vector_size (int): Dimension of the embedding vector.
        """
        self.cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.collection_name} (
                id VARCHAR(36) PRIMARY KEY,
                vector VECTOR({vector_size}),
                payload JSON
            )
        """
        )
        self.conn.commit()

    def insert(self, vectors, payloads=None, ids=None):
        """
        Insert vectors into a collection.

        Args:
            vectors (List[List[float]]): List of vectors to insert.
            payloads (List[Dict], optional): List of payloads corresponding to vectors.
            ids (List[str], optional): List of IDs corresponding to vectors.
        """
        if not vectors:
            return

        if ids is None:
            import uuid

            ids = [str(uuid.uuid4()) for _ in vectors]

        if payloads is None:
            payloads = [{} for _ in vectors]

        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")

        for id, vector, payload in zip(ids, vectors, payloads):
            vector_str = f"[{','.join(map(str, vector))}]"
            payload_str = json.dumps(payload)

            self.cur.execute(
                f"INSERT INTO {self.collection_name} (id, vector, payload) VALUES (%s, %s, %s)",
                (id, vector_str, payload_str),
            )

        self.conn.commit()

    def search(self, vectors, limit=5, filters=None):
        """
        Search for similar vectors.

        Args:
            vectors (List[float]): Query vector.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """
        vector_str = f"[{','.join(map(str, vectors))}]"

        filter_conditions = []
        filter_params = []

        if filters:
            for k, v in filters.items():
                filter_conditions.append(f"JSON_EXTRACT(payload, '$.{k}') = %s")
                filter_params.append(str(v))

        filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""

        query_sql = f"""
            SELECT id, vec_cosine_distance(vector, %s) AS distance, payload
            FROM {self.collection_name}
            {filter_clause}
            ORDER BY distance
            LIMIT %s
        """

        params = [vector_str] + filter_params + [limit]
        self.cur.execute(query_sql, params)

        results = self.cur.fetchall()
        return [OutputData(id=str(r[0]), score=float(r[1]), payload=json.loads(r[2]) if r[2] else {}) for r in results]

    def delete(self, vector_id):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        self.cur.execute(f"DELETE FROM {self.collection_name} WHERE id = %s", (vector_id,))
        self.conn.commit()

    def update(self, vector_id, vector=None, payload=None):
        """
        Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (List[float], optional): Updated vector.
            payload (Dict, optional): Updated payload.
        """
        if vector:
            vector_str = f"[{','.join(map(str, vector))}]"
            self.cur.execute(f"UPDATE {self.collection_name} SET vector = %s WHERE id = %s", (vector_str, vector_id))
        if payload:
            # Get existing payload and merge
            self.cur.execute(f"SELECT payload FROM {self.collection_name} WHERE id = %s", (vector_id,))
            result = self.cur.fetchone()
            if result and result[0]:
                existing_payload = json.loads(result[0])
                existing_payload.update(payload)
                payload = existing_payload

            self.cur.execute(
                f"UPDATE {self.collection_name} SET payload = %s WHERE id = %s", (json.dumps(payload), vector_id)
            )
        self.conn.commit()

    def get(self, vector_id) -> OutputData:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector.
        """
        self.cur.execute(f"SELECT id, vector, payload FROM {self.collection_name} WHERE id = %s", (vector_id,))
        result = self.cur.fetchone()
        if not result:
            return None

        return OutputData(id=str(result[0]), score=None, payload=json.loads(result[2]) if result[2] else {})

    def list_cols(self) -> List[str]:
        """
        List all collections.

        Returns:
            List[str]: List of collection names.
        """
        self.cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE()")
        return [row[0] for row in self.cur.fetchall()]

    def delete_col(self):
        """Delete a collection."""
        self.cur.execute(f"DROP TABLE IF EXISTS {self.collection_name}")
        self.conn.commit()

    def col_info(self):
        """
        Get information about a collection.

        Returns:
            Dict[str, Any]: Collection information.
        """
        self.cur.execute(
            f"""
            SELECT 
                %s as table_name,
                (SELECT COUNT(*) FROM {self.collection_name}) as row_count,
                (SELECT data_length + index_length FROM information_schema.tables 
                 WHERE table_schema = DATABASE() AND table_name = %s) as total_size
            """,
            (self.collection_name, self.collection_name),
        )
        result = self.cur.fetchone()
        return {"name": result[0], "count": result[1], "size": result[2]}

    def list(self, filters=None, limit=100):
        """
        List all vectors in a collection.

        Args:
            filters (Dict, optional): Filters to apply to the list.
            limit (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            List[OutputData]: List of vectors.
        """
        filter_conditions = []
        filter_params = []

        if filters:
            for k, v in filters.items():
                filter_conditions.append(f"JSON_EXTRACT(payload, '$.{k}') = %s")
                filter_params.append(str(v))

        filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""

        query = f"""
            SELECT id, vector, payload
            FROM {self.collection_name}
            {filter_clause}
            LIMIT %s
        """

        self.cur.execute(query, filter_params + [limit])

        results = self.cur.fetchall()
        return [[OutputData(id=str(r[0]), score=None, payload=json.loads(r[2]) if r[2] else {}) for r in results]]

    def __del__(self):
        """
        Close the database connection when the object is deleted.
        """
        if hasattr(self, "cur"):
            self.cur.close()
        if hasattr(self, "conn"):
            self.conn.close()

    def reset(self):
        """Reset the index by deleting and recreating it."""
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.create_col(self.embedding_model_dims)
