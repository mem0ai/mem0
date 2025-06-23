import json
import logging
import os
import shutil
import uuid
from typing import Dict, Optional

import lancedb
import pyarrow as pa
from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[Dict]


class LanceDB(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        embedding_model_dims: int,
        uri: str = None,
        api_key: str = None,
        region: str = None,
        on_disk: bool = False,
        storage_options: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the LanceDB vector store.

        Args:
            collection_name (str): Name of the table (collection).
            embedding_model_dims (int): Dimensions of the embedding model.
            uri (str, optional): URI for LanceDB database. Defaults to './lancedb'.
            api_key (str, optional): API key for LanceDB Enterprise.
            region (str, optional): Cloud region for LanceDB Enterprise.
            on_disk (bool, optional): Enables persistent storage. Defaults to False.
            storage_options (Dict, optional): Options for connecting to cloud storage. Defaults to None.
        """
        if uri is None:
            uri = "./lancedb"
        connect_kwargs = {"uri": uri}
        if api_key:
            connect_kwargs["api_key"] = api_key
        if region:
            connect_kwargs["region"] = region
        if not on_disk and os.path.exists(uri) and uri.startswith("./"):
            shutil.rmtree(uri)
        self.db = lancedb.connect(**connect_kwargs)
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.create_col(collection_name, embedding_model_dims, None)

    def create_col(self, name, vector_size, distance):
        """
        Create a new table (collection) if it doesn't exist.

        Args:
            name (str): Name of the table to create.
            vector_size (int): Dimension of the vector.
            distance: Not used (for API compatibility).
        """
        if name in self.db.table_names():
            logger.debug(f"Table {name} already exists. Skipping creation.")
            return
        schema = pa.schema(
            [
                pa.field("id", pa.string(), nullable=False),
                pa.field("vector", pa.list_(pa.float32(), vector_size)),
                pa.field("payload", pa.string(), nullable=True),
            ]
        )
        self.db.create_table(name, schema=schema)

    def insert(self, vectors, payloads=None, ids=None):
        """
        Insert vectors into the table.

        Args:
            vectors (list): List of vectors to insert.
            payloads (list, optional): List of payloads corresponding to vectors. Defaults to None.
            ids (list, optional): List of IDs corresponding to vectors. Defaults to None.
        """
        logger.info(f"Inserting {len(vectors)} vectors into table {self.collection_name}")
        if payloads is None:
            payloads = [{}] * len(vectors)
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in vectors]
        processed_payloads = []
        for payload in payloads:
            if not isinstance(payload, dict):
                payload = {}
            payload.setdefault("data", "")
            payload.setdefault("user_id", None)
            payload.setdefault("agent_id", None)
            payload.setdefault("run_id", None)
            processed_payloads.append(payload)
        json_payloads = [json.dumps(p) for p in processed_payloads]
        data = {
            "id": ids,
            "vector": vectors,
            "payload": json_payloads,
        }
        arrow_table = pa.Table.from_pydict(data)
        table = self.db.open_table(self.collection_name)
        table.add(arrow_table)

    def search(self, query, vectors, limit=5, filters=None):
        """
        Search for similar vectors in the table.

        Args:
            query: Not used (for API compatibility).
            vectors (list): The query vector to search for.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            List[OutputData]: Search results.
        """
        table = self.db.open_table(self.collection_name)
        if not vectors or not isinstance(vectors, list):
            return []
        query_vector = vectors
        # Only use the supported search API
        results = table.search(query_vector).limit(limit).to_pandas()
        parsed_results = []
        for record in results.to_dict(orient="records"):
            payload = json.loads(record["payload"])
            if not filters or all(payload.get(k) == v for k, v in filters.items()):
                parsed_results.append(
                    OutputData(id=record["id"], score=record.get("score", 1.0), payload=payload)
                )
        return parsed_results

    def delete(self, vector_id):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        table = self.db.open_table(self.collection_name)
        table.delete(f"id = '{vector_id}'")

    def update(self, vector_id, vector=None, payload=None):
        """
        Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (list, optional): Updated vector. Defaults to None.
            payload (dict, optional): Updated payload. Defaults to None.
        """
        existing_record = self.get(vector_id)
        if not existing_record:
            raise ValueError(f"No vector found with ID {vector_id}")
        if payload:
            existing_payload = existing_record.payload or {}
            existing_payload.update(payload)
            payload = existing_payload
        self.delete(vector_id)
        self.insert(
            vectors=[vector or getattr(existing_record, "vector", None)],
            payloads=[payload or existing_record.payload],
            ids=[vector_id],
        )

    def get(self, vector_id):
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            OutputData or None: Retrieved vector or None if not found.
        """
        table = self.db.open_table(self.collection_name)
        result = table.to_pandas().query(f"id == '{vector_id}'")
        if result.empty:
            return None
        record = result.to_dict(orient="records")[0]
        payload = json.loads(record["payload"])
        return OutputData(id=record["id"], score=1.0, payload=payload)

    def list_cols(self):
        """
        List all tables (collections) in the database.

        Returns:
            list: List of table (collection) names.
        """
        return self.db.table_names()

    def delete_col(self):
        """
        Delete the entire table (collection) and recreate it.
        """
        self.db.drop_table(self.collection_name)
        self.create_col(self.collection_name, self.embedding_model_dims, None)

    def col_info(self):
        """
        Get information about the current table (collection) schema.

        Returns:
            dict: Schema information for the table.
        """
        table = self.db.open_table(self.collection_name)
        schema = table.schema()
        return {"fields": [{"name": f.name, "type": str(f.type), "nullable": f.nullable} for f in schema]}

    def list(self, filters=None, limit=100):
        """
        List all vectors in the table, optionally filtered.

        Args:
            filters (dict, optional): Filters to apply. Defaults to None.
            limit (int, optional): Maximum number of results to return. Defaults to 100.

        Returns:
            list: A list containing a list of OutputData objects matching the filters.
        """
        table = self.db.open_table(self.collection_name)
        dummy_vector = [0.0] * self.embedding_model_dims
        results = table.search(dummy_vector).limit(limit).to_pandas()
        filtered_records = []
        for record in results.to_dict(orient="records"):
            payload = json.loads(record["payload"])
            if not filters or all(payload.get(k) == v for k, v in filters.items()):
                filtered_records.append(OutputData(id=record["id"], score=1.0, payload=payload))
        return [filtered_records]

    def reset(self):
        """
        Reset the table by deleting and recreating it.
        """
        logger.warning(f"Resetting table {self.collection_name}...")
        self.delete_col()
