import logging
import os
import shutil
import pandas as pd
import lancedb
import json
import uuid
import pyarrow as pa
from typing import Dict, Optional, List, Union, Any

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

class LanceDB(VectorStoreBase):
    def __init__(
        self,
        table_name: str,
        embedding_model_dims: int,
        uri: str = None,
        on_disk: bool = False,
        storage_options: Optional[Dict[str,str]] = None
    ):
        """
        Initialize the LanceDB vector store.

        Args:
            table_name (str): Name of the table.
            embedding_model_dims (int): Dimensions of the embedding model.
            uri (str): URI for LanceDB database.
            on_disk (bool, optional): Enables persistent storage. Defaults to False.
            storage_options (Dict, optional): Options for connecting to cloud storage. Defaults to None.
        """
        if uri is None:
            uri = "./lancedb"
        if not on_disk and os.path.exists(uri):
            shutil.rmtree(uri)
        self.db = lancedb.connect(uri)
        self.table_name = table_name
        self.embedding_model_dims = embedding_model_dims
        self.create_table()

    def create_table(self):
        """
        Create a new table if it doesn't exist.
        """
        if self.table_name in self.db.table_names():
            logger.debug(f"Table {self.table_name} already exists. Skipping creation.")
            return

        schema = pa.schema([
            pa.field("id", pa.string(), nullable=False),
            pa.field("vector", pa.list_(pa.float32(), self.embedding_model_dims)),
            pa.field("payload", pa.string(), nullable=True)
        ])
        self.db.create_table(self.table_name, schema=schema)

    def insert(self, vectors: list, payloads: list = None, ids: list = None):
        """
        Insert vectors into the table.

        Args:
            vectors (list): List of vectors to insert.
            payloads (list, optional): List of payloads corresponding to vectors. Defaults to None.
            ids (list, optional): List of IDs corresponding to vectors. Defaults to None.
        """
        logger.info(f"Inserting {len(vectors)} vectors into table {self.table_name}")

        if payloads is None:
            payloads = [{}] * len(vectors)
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in vectors]

        processed_payloads = []
        for payload in payloads:
            if not isinstance(payload, dict):
                payload = {}

            payload.setdefault('data', '')
            payload.setdefault('user_id', None)
            payload.setdefault('agent_id', None)
            payload.setdefault('run_id', None)
            
            processed_payloads.append(payload)

        json_payloads = [json.dumps(p) for p in processed_payloads]

        data = {
            "id": ids,
            "vector": vectors,
            "payload": json_payloads,
        }

        arrow_table = pa.Table.from_pydict(data)

        table = self.db.open_table(self.table_name)
        table.add(arrow_table)

    def search(self, query: list, limit: int = 5, filters: dict = None) -> list:
        """
        Search for similar vectors.

        Args:
            query (list): Query vector.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """
        table = self.db.open_table(self.table_name)
        query_builder = table.search(query).limit(limit)

        if filters:
            filtered_results = []
            for record in table.to_pandas().to_dict(orient='records'):
                payload = json.loads(record['payload'])
                
                if all(payload.get(k) == v for k, v in filters.items()):
                    result = type('MemoryResult', (), {
                        'id': record['id'],
                        'payload': payload,
                        'score': 1.0
                    })
                    filtered_results.append(result)
            
            return filtered_results

        results = query_builder.to_pandas()
        parsed_results = []
        for record in results.to_dict(orient='records'):
            result = type('MemoryResult', (), {
                'id': record['id'],
                'payload': json.loads(record['payload']),
                'score': record.get('score', 1.0)
            })
            parsed_results.append(result)

        return parsed_results

    def list(self, filters: dict = None, limit: int = 100) -> list:
        """
        List vectors with optional filtering.

        Args:
            filters (dict, optional): Filters to apply. Defaults to None.
            limit (int, optional): Maximum number of results. Defaults to 100.

        Returns:
            list: List of matching vectors.
        """
        table = self.db.open_table(self.table_name)
        df = table.to_pandas()

        filtered_records = []
        for record in df.to_dict(orient='records'):
            payload = json.loads(record['payload'])

            if not filters or all(payload.get(k) == v for k, v in filters.items()):
                result = type('MemoryResult', (), {
                    'id': record['id'],
                    'payload': payload
                })
                filtered_records.append(result)


        return [filtered_records[:limit]]

    def get(self, vector_id: str) -> Optional[dict]:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            Optional[dict]: Retrieved vector or None.
        """
        table = self.db.open_table(self.table_name)
        result = table.to_pandas().query(f"id == '{vector_id}'")

        if result.empty:
            return None

        record = result.to_dict(orient='records')[0]
        payload = json.loads(record['payload'])
        
        result = type('MemoryResult', (), {
            'id': record['id'],
            'payload': payload
        })

        return result

    def update(self, vector_id: str, vector: list = None, payload: dict = None):
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
            existing_payload = existing_record['payload']
            existing_payload.update(payload)
            payload = existing_payload

        self.delete(vector_id)
        self.insert(
            vectors=[vector or existing_record['vector']],
            payloads=[payload or existing_record['payload']],
            ids=[vector_id]
        )

    def delete(self, vector_id: str):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        table = self.db.open_table(self.table_name)
        table.delete(f"id = '{vector_id}'")

    def delete_col(self):
        """
        Delete the entire table.
        """
        self.db.drop_table(self.table_name)
        self.create_table()

    def list_tables(self) -> list:
        """
        List all tables.

        Returns:
            list: List of table names.
        """
        return self.db.table_names()

    def col_info(self, col_name: str) -> dict:
        """
        Retrieve information about a specific column.

        Args:
            col_name (str): Name of the column.

        Returns:
            dict: Column information.
        """
        table = self.db.open_table(self.table_name)
        schema = table.schema()
        column = schema.get(col_name)

        if column:
            return {
                "name": column.name,
                "type": str(column.type),
                "nullable": column.nullable,
                "metadata": column.metadata or {}
            }
        else:
            raise ValueError(f"Column {col_name} does not exist in table {self.table_name}")

    def create_col(self, col_name: str, col_type: str, nullable: bool = True, metadata: dict = None):
        """
        Add a new column to the table.

        Args:
            col_name (str): Name of the new column.
            col_type (str): Data type of the new column.
            nullable (bool, optional): Whether the column can contain null values. Defaults to True.
            metadata (dict, optional): Additional metadata for the column. Defaults to None.
        """
        table = self.db.open_table(self.table_name)
        schema = table.schema()

        if col_name in schema.names:
            raise ValueError(f"Column {col_name} already exists in table {self.table_name}")

        type_mapping = {
            'string': pa.string(),
            'int': pa.int64(),
            'float': pa.float64(),
            'bool': pa.bool_(),
        }

        arrow_type = type_mapping.get(col_type.lower())
        if not arrow_type:
            raise ValueError(f"Unsupported column type: {col_type}")

        new_field = pa.field(col_name, arrow_type, nullable=nullable, metadata=metadata)

        new_schema = schema.append(new_field)
        table.alter(new_schema)

    def list_cols(self) -> List[str]:
        """
        List all columns in the table.

        Returns:
            List[str]: List of column names.
        """
        table = self.db.open_table(self.table_name)
        return table.schema().names