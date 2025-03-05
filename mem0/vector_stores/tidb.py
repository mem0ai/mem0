import json
import logging
from typing import List, Optional
from pydantic import BaseModel

from mem0.configs.vector_stores.tidb import IndexMethod, DistanceMetric

try:
    import pymysql
except ImportError:
    raise ImportError("The 'pymysql' library is required. Please install it using 'pip install pymysql'.")

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


def encode_vector(vector) -> str:
    return f"[{', '.join(map(str, vector))}]"

class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class TiDB(VectorStoreBase):
    def __init__(
        self,
        database,
        collection_name,
        embedding_model_dims,
        user,
        password,
        host,
        port,
        index_method,
        distance_metric,
    ):
        """
        Initialize the TiDB database.

        Args:
            database (str): Database name
            collection_name (str): Collection name
            embedding_model_dims (int): Dimension of the embedding vector
            user (str): Database user
            password (str): Database password
            host (str, optional): Database host
            port (int, optional): Database port
            index_method (IndexMethod, optional): Index method to use. Defaults to HNSW.
            distance_metric (DistanceMetric, optional): Index measure to use. Defaults to COSINE.
        """
        self.collection_name = collection_name
        self.index_method = index_method or IndexMethod.HNSW
        self.distance_metric = distance_metric or DistanceMetric.COSINE
        self.conn = pymysql.connect(database=database, user=user, password=password, host=host, port=port)
        self.cur = self.conn.cursor()

        collections = self.list_cols()
        if collection_name not in collections:
            self.create_col(embedding_model_dims)

    def create_col(self, embedding_model_dims):
        """
        Create a new collection (table in TiDB).
        Will also initialize vector search index if specified.

        Args:
            embedding_model_dims (int): Dimension of the embedding vector.
        """
        self.cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.collection_name} (
                id CHAR(36) PRIMARY KEY,
                vector vector({embedding_model_dims}),
                payload JSON
            );
        """
        )

        if self.index_method == IndexMethod.HNSW:
            self.cur.execute(
                f"""
                ALTER TABLE {self.collection_name} SET TIFLASH REPLICA 1
            """
            )
            self.cur.execute(
                f"""
                ALTER TABLE {self.collection_name}
                ADD VECTOR INDEX vec_idx_vector_{self.collection_name} (({self.distance_metric.to_sql_func()}(vector)))
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
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")
        json_payloads = [json.dumps(payload) for payload in payloads]

        data = [(id, encode_vector(vector), payload) for id, vector, payload in zip(ids, vectors, json_payloads)]
        self.cur.executemany(
            f"INSERT INTO {self.collection_name} (id, vector, payload) VALUES (%s, %s, %s)",
            data,
        )
        self.conn.commit()

    def search(self, query, limit=5, filters=None):
        """
        Search for similar vectors.

        Args:
            query (List[float]): Query vector.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """
        filter_conditions = []
        filter_params = []

        if filters:
            for k, v in filters.items():
                filter_conditions.append("payload->>%s = %s")
                filter_params.extend([f"$.{k}", str(v)])

        filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""

        self.cur.execute(
            f"""
            SELECT id, {self.distance_metric.to_sql_func()}(vector, %s) AS distance, payload
            FROM {self.collection_name}
            {filter_clause}
            ORDER BY distance
            LIMIT %s
        """,
            (encode_vector(query), *filter_params, limit),
        )

        results = self.cur.fetchall()
        return [OutputData(id=str(r[0]), score=float(r[1]), payload=json.loads(r[2]) if r[2] else None) for r in results]

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
            self.cur.execute(
                f"UPDATE {self.collection_name} SET vector = %s WHERE id = %s",
                (encode_vector(vector), vector_id),
            )
        if payload:
            self.cur.execute(
                f"UPDATE {self.collection_name} SET payload = %s WHERE id = %s",
                (json.dumps(payload), vector_id),
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
        self.cur.execute(
            f"SELECT id, vector, payload FROM {self.collection_name} WHERE id = %s",
            (vector_id,),
        )
        result = self.cur.fetchone()
        if not result:
            return None
        payload = json.loads(result[2]) if result[2] else None
        return OutputData(id=str(result[0]), score=None, payload=payload)

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
            """
            SELECT 
                table_name, 
                TABLE_ROWS as row_count,
                FORMAT_BYTES(data_length + index_length) as total_size
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() AND table_name = %s
        """,
            (self.collection_name,),
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
                filter_conditions.append("payload->>%s = %s")
                filter_params.extend([f"$.{k}", str(v)])

        filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""

        query = f"""
            SELECT id, vector, payload
            FROM {self.collection_name}
            {filter_clause}
            LIMIT %s
        """

        self.cur.execute(query, (*filter_params, limit))

        results = self.cur.fetchall()
        return [[
            OutputData(id=str(r[0]), score=None, payload=json.loads(r[2]) if r[2] else None)
            for r in results
        ]]

    def __del__(self):
        """
        Close the database connection when the object is deleted.
        """
        if hasattr(self, "cur"):
            self.cur.close()
        if hasattr(self, "conn"):
            self.conn.close()
