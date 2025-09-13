import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

try:
    from cassandra.cluster import Cluster
    from cassandra.auth import PlainTextAuthProvider
except ImportError:
    raise ImportError("The 'cassandra driver' library is required. Please install it using 'pip install cassandra-driver'.")

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # distance
    payload: Optional[Dict]  # metadata


class CassandraDB(VectorStoreBase):
    VECTOR_TYPE = "FLOAT"
    SIMILARITY_METRIC = "cosine"
    TOP_K = 1000

    def __init__(self, keyspace: str, table: str, username: str, pwd: str, embedding_model_dims: int = 1024, host: str = "127.0.0.1", port: int = 9042, protocol: str = 'cass'):
        self.username = username
        self.pwd = pwd
        self.keyspace = keyspace
        self.table = table
        self.embedding_model_dims = embedding_model_dims

        auth_provider = PlainTextAuthProvider(username=self.username, password=self.pwd)
        self.cluster = Cluster(host=host, port=port, protocol=protocol, auth_provider=auth_provider)
        self.session = self.cluster.connect()

    def create_col(self):
        """Create new collection(table) with vector search index."""
        self.session.execute("CREATE KEYSPACE IF NOT EXISTS " + self.keyspace + " WITH REPLICATION = { 'class': 'SimpleStrategy', 'replication_factor' : 3 } ")
        self.session.execute(
                   "CREATE TABLE IF NOT EXISTS  " + self.keyspace  + "." + self.table + "(" +
                       " id UUID PRIMARY KEY," +
                       " vector VECTOR <" + self.VECTOR_TYPE + "," + self.embedding_model_dims  + ">," +
                       " payload BLOB)"
        )
        self.session.execute("CREATE INDEX IF NOT EXISTS " + self.keyspace + "." + self.table + "_vectoridx(vector) USING 'sai' WITH OPTIONS = {'similarity_function' : ' " + self.SIMILARITY_METRIC +"'}")

    def insert(self, vectors, payloads=None, ids=None):
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.keyspace}.{self.table}")

        data = [(id, vector, payload) for id, vector, payload in zip(ids, vectors, payloads)]
        self.session.execute(
            f"INSERT INTO {self.collection_name} (id, vector, payload) VALUES %s",
            data,
        )

    def search(self, query, vectors, limit=5, filters=None):
        results = self.session.execute(
            f"""
               SELECT *
               FROM {self.keyspace}.{self.table}
               ORDER BY vector ANN OF %s 
               LIMIT %d
           """,
            (vectors, limit),
        ).fetchall()

        return [OutputData(id=str(r[0]), score=float(r[1]), payload=r[2]) for r in results]

    def delete(self, vector_id):
        self.session.execute(f"DELETE FROM {self.keyspace}.{self.table}  WHERE id = %s", (vector_id,))

    def update(self, vector_id, vector=None, payload=None):
        if vector:
            self.cur.execute(
                f"UPDATE {self.keyspace}.{self.table} SET vector = %s WHERE id = %s",
                (vector, vector_id),
            )
        if payload:
            self.cur.execute(
                f"UPDATE {self.keyspace}.{self.table} SET payload = %s WHERE id = %s",
                (payload, vector_id),
            )

    def get(self, vector_id) -> OutputData:
        result = self.session.execute(
            f"SELECT id, vector, payload FROM {self.keyspace}.{self.table} WHERE id = %s",
            (vector_id,),
        ).one()

        if not result:
            return None
        return OutputData(id=str(result[0]), score=None, payload=result[2])

    def delete_col(self):
        self.session.execute("DROP INDEX IF EXISTS " + self.keyspace + "." + self.table + "_vectoridx")
        self.session.execute(f"DROP TABLE IF EXISTS {self.keyspace}.{self.table}")

    def col_info(self):
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

    def __del__(self):
        self.session.close().close()

    def reset(self):
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.create_col(self.embedding_model_dims)
