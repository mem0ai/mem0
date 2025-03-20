import json
import logging
from typing import List, Optional

from pydantic import BaseModel

try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    raise ImportError("The 'psycopg2' library is required. Please install it using 'pip install psycopg2'.")

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class PGVector(VectorStoreBase):
    def __init__(
        self,
        dbname,
        collection_name,
        embedding_model_dims,
        user,
        password,
        host,
        port,
        diskann,
        hnsw,
    ):
        """
        Initialize the PGVector database.

        Args:
            dbname (str): Database name
            collection_name (str): Collection name
            embedding_model_dims (int): Dimension of the embedding vector
            user (str): Database user
            password (str): Database password
            host (str, optional): Database host
            port (int, optional): Database port
            diskann (bool, optional): Use DiskANN for faster search
            hnsw (bool, optional): Use HNSW for faster search
        """
        self.collection_name = collection_name
        self.use_diskann = diskann
        self.use_hnsw = hnsw

        self.conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)
        self.cur = self.conn.cursor()

        collections = self.list_cols()
        if collection_name not in collections:
            self.create_col(embedding_model_dims)

    def create_col(self, embedding_model_dims):
        """
        Create a new collection (table in PostgreSQL).
        Will also initialize vector search index if specified.

        Args:
            embedding_model_dims (int): Dimension of the embedding vector.
        """
        self.cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.collection_name} (
                id UUID PRIMARY KEY,
                vector vector({embedding_model_dims}),
                payload JSONB
            );
        """
        )

        if self.use_diskann and embedding_model_dims < 2000:
            # Check if vectorscale extension is installed
            self.cur.execute("SELECT * FROM pg_extension WHERE extname = 'vectorscale'")
            if self.cur.fetchone():
                # Create DiskANN index if extension is installed for faster search
                self.cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS {self.collection_name}_diskann_idx
                    ON {self.collection_name}
                    USING diskann (vector);
                """
                )
        elif self.use_hnsw:
            self.cur.execute(
                f"""
                CREATE INDEX IF NOT EXISTS {self.collection_name}_hnsw_idx
                ON {self.collection_name}
                USING hnsw (vector vector_cosine_ops)
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

        data = [(id, vector, payload) for id, vector, payload in zip(ids, vectors, json_payloads)]
        execute_values(
            self.cur,
            f"INSERT INTO {self.collection_name} (id, vector, payload) VALUES %s",
            data,
        )
        self.conn.commit()

    def search(self, query, vectors, limit=5, filters=None):
        """
        Search for similar vectors.

        Args:
            query (str): Query.
            vectors (List[float]): Query vector.
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
                filter_params.extend([k, str(v)])

        filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""

        self.cur.execute(
            f"""
            SELECT id, vector <=> %s::vector AS distance, payload
            FROM {self.collection_name}
            {filter_clause}
            ORDER BY distance
            LIMIT %s
        """,
            (vectors, *filter_params, limit),
        )

        results = self.cur.fetchall()
        return [OutputData(id=str(r[0]), score=float(r[1]), payload=r[2]) for r in results]

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
                (vector, vector_id),
            )
        if payload:
            self.cur.execute(
                f"UPDATE {self.collection_name} SET payload = %s WHERE id = %s",
                (psycopg2.extras.Json(payload), vector_id),
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
        return OutputData(id=str(result[0]), score=None, payload=result[2])

    def list_cols(self) -> List[str]:
        """
        List all collections.

        Returns:
            List[str]: List of collection names.
        """
        self.cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
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
                table_name, 
                (SELECT COUNT(*) FROM {self.collection_name}) as row_count,
                (SELECT pg_size_pretty(pg_total_relation_size('{self.collection_name}'))) as total_size
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = %s
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
                filter_params.extend([k, str(v)])

        filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""

        query = f"""
            SELECT id, vector, payload
            FROM {self.collection_name}
            {filter_clause}
            LIMIT %s
        """

        self.cur.execute(query, (*filter_params, limit))

        results = self.cur.fetchall()
        return [[OutputData(id=str(r[0]), score=None, payload=r[2]) for r in results]]

    def __del__(self):
        """
        Close the database connection when the object is deleted.
        """
        if hasattr(self, "cur"):
            self.cur.close()
        if hasattr(self, "conn"):
            self.conn.close()
