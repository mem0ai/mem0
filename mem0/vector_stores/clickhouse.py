import logging
from mem0.vector_stores.base import VectorStoreBase
import clickhouse_connect
import json
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)



@dataclass
class OutputData:
    """A single result row, exposing fields as attributes (result.id, not
    result["id"]) to match the shape mem0's internal code expects — the same
    convention Qdrant's own client objects follow."""

    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]
    vector: Optional[Any] = None


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
    ):
        """
        Initialize the ClickHouse vector store.

        Args:
            collection_name (str): Name of the collection (maps to a ClickHouse table).
            embedding_model_dims (int): Dimensions of the embedding vectors.
            host (str): ClickHouse server host. Defaults to "localhost".
            port (int): ClickHouse server port (HTTP interface). Defaults to 8123.
            username (str): Username for authentication. Defaults to "default".
            password (str): Password for authentication. Defaults to "".
            database (str): Database name. Defaults to "default".
        """

        self.client = clickhouse_connect.get_client(
            host=host,
            port=port,
            username=username,
            password=password,
            database=database,
        )


        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.create_col(collection_name, embedding_model_dims, distance="cosine")

    def create_col(self, name, vector_size, distance):
        """
        Create a new collection (ClickHouse table) if it doesn't already exist.

        Args:
            name (str): Name of the table to create.
            vector_size (int): Dimensionality of the embedding vectors.
            distance (str): Distance metric name (kept for interface compatibility;
                ClickHouse similarity is computed at query time in search()).
        """
        # Skip creation if the table already exists
        existing = self.list_cols()
        if name in existing:
            logger.debug(f"Collection {name} already exists. Skipping creation.")
            return

        # id: unique identifier for each memory
        # vector: the embedding, stored as an array of 32-bit floats
        # payload: arbitrary metadata (user_id, text, etc.) stored as JSON text
        query = f"""
        CREATE TABLE IF NOT EXISTS {name} (
            id String,
            vector Array(Float32),
            payload String
        ) ENGINE = MergeTree()
        ORDER BY id
        """
        self.client.command(query)
        logger.info(f"Created collection {name}")


    def insert(self, vectors, payloads=None, ids=None):
        """
        Insert vectors into the collection.

        Args:
            vectors (list): List of embedding vectors (each a list of floats).
            payloads (list, optional): List of metadata dicts, one per vector.
            ids (list, optional): List of string IDs, one per vector. If not
                provided, the row's position (as a string) is used instead.
        """
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")

        row_ids = [str(ids[idx]) if ids is not None else str(idx) for idx in range(len(vectors))]

        # Remove any existing rows with these IDs first, so re-inserting the
        # same ID replaces it instead of creating a duplicate.
        id_list = ", ".join(f"'{rid}'" for rid in row_ids)
        self.client.command(f"ALTER TABLE {self.collection_name} DELETE WHERE id IN ({id_list})")


        rows = []
        for idx, vector in enumerate(vectors):
            row_id = str(ids[idx]) if ids is not None else str(idx)
            payload = payloads[idx] if payloads else {}
            # payload is a Python dict; the table column is a String, so we
            # serialize it to JSON text before storing it.
            payload_json = json.dumps(payload)
            rows.append([row_id, vector, payload_json])

        self.client.insert(
            self.collection_name,
            rows,
            column_names=["id", "vector", "payload"],
        )


    def search(self, query, vectors, top_k=5, filters=None):
        """
        Search for similar vectors using cosine similarity.

        Args:
            query (str): The query text (unused here; ClickHouse compares raw vectors).
            vectors (list): The query embedding vector to compare against.
            top_k (int): Number of results to return. Defaults to 5.
            filters (dict, optional): Simple equality filters on payload fields.
                Not yet implemented for ClickHouse (basic version).

        Returns:
            list: Rows with id, score (higher = more similar), and payload.
        """
        sql = f"""
        SELECT
            id,
            1 - cosineDistance(vector, {vectors}) AS score,
            payload
        FROM {self.collection_name}
        ORDER BY score DESC
        LIMIT {top_k}
        """
        result = self.client.query(sql)

        results = []
        for row in result.result_rows:
            row_id, score, payload_json = row
            payload = json.loads(payload_json)
            results.append(OutputData(id=row_id, score= score, payload= payload))
        return results


    def delete(self, vector_id):
        """
        Delete a vector by ID.

        Args:
            vector_id: ID of the vector to delete.
        """
        self.client.command(
            f"ALTER TABLE {self.collection_name} DELETE WHERE id = '{vector_id}'"
        )

    def get(self, vector_id):
        """
        Retrieve a vector by ID.

        Args:
            vector_id: ID of the vector to retrieve.

        Returns:
            dict or None: {"id": ..., "vector": ..., "payload": ...}, or None if not found.
        """
        result = self.client.query(
            f"SELECT id, vector, payload FROM {self.collection_name} WHERE id = '{vector_id}'"
        )
        if not result.result_rows:
            return None
        row_id, vector, payload_json = result.result_rows[0]
        return OutputData(id=row_id, score=None, payload=json.loads(payload_json), vector=vector)


    def update(self, vector_id, vector=None, payload=None):
        """
        Update a vector and/or its payload. Implemented as delete-then-insert,
        since ClickHouse's MergeTree engine has no native in-place update.
        Any field not provided is kept from the existing row.

        Args:
            vector_id: ID of the vector to update.
            vector (list, optional): New vector. If omitted, the existing vector is kept.
            payload (dict, optional): New payload. If omitted, the existing payload is kept.
        """
        existing = self.get(vector_id)
        if existing is None:
            logger.warning(f"update() called with unknown id {vector_id}; nothing to update.")
            return

        new_vector = vector if vector is not None else existing.vector
        new_payload = payload if payload is not None else existing.payload

        self.insert(vectors=[new_vector], payloads=[new_payload], ids=[vector_id])


    def list_cols(self):
        """List all collections (tables)."""
        result = self.client.query("SHOW TABLES")
        return [row[0] for row in result.result_rows]


    def delete_col(self):
        """Delete the collection (drop the table entirely)."""
        self.client.command(f"DROP TABLE IF EXISTS {self.collection_name}")


    def col_info(self):
        """
        Get information about the collection.

        Returns:
            dict: Basic info about the collection, e.g. row count.
        """
        result = self.client.query(f"SELECT count() FROM {self.collection_name}")
        row_count = result.result_rows[0][0]
        return {"name": self.collection_name, "row_count": row_count}


    def list(self, filters=None, top_k=None):
        """
        List vectors in the collection.

        Args:
            filters (dict, optional): Not yet implemented for ClickHouse (basic version).
            top_k (int, optional): Maximum number of rows to return. Defaults to 100.

        Returns:
            list: Rows with id, vector, and payload.
        """
        limit = top_k if top_k is not None else 100
        result = self.client.query(
            f"SELECT id, vector, payload FROM {self.collection_name} LIMIT {limit}"
        )
        rows = []
        for row_id, vector, payload_json in result.result_rows:
            rows.append(OutputData(id=row_id, score=None, payload=json.loads(payload_json), vector=vector))
        return rows


    def reset(self):
        """Delete and recreate the collection."""
        logger.warning(f"Resetting collection {self.collection_name}...")
        self.delete_col()
        self.create_col(self.collection_name, self.embedding_model_dims, distance="cosine")


