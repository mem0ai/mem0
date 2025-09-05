import json
import logging
import uuid
from typing import Optional, List
from datetime import datetime, date
from databricks.sdk.service.catalog import ColumnInfo, ColumnTypeName, TableType, DataSourceFormat
from databricks.sdk.service.catalog import TableConstraint, PrimaryKeyConstraint
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.vectorsearch import (
    VectorIndexType,
    DeltaSyncVectorIndexSpecRequest,
    DirectAccessVectorIndexSpec,
    EmbeddingSourceColumn,
    EmbeddingVectorColumn,
)
from pydantic import BaseModel
from mem0.memory.utils import extract_json
from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class MemoryResult(BaseModel):
    id: Optional[str] = None
    score: Optional[float] = None
    payload: Optional[dict] = None


excluded_keys = {"user_id", "agent_id", "run_id", "hash", "data", "created_at", "updated_at"}


class Databricks(VectorStoreBase):
    def __init__(
        self,
        workspace_url: str,
        access_token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        azure_client_id: Optional[str] = None,
        azure_client_secret: Optional[str] = None,
        endpoint_name: str = None,
        catalog: str = None,
        schema: str = None,
        table_name: str = None,
        collection_name: str = "mem0",
        index_type: str = "DELTA_SYNC",
        embedding_model_endpoint_name: Optional[str] = None,
        embedding_dimension: int = 1536,
        endpoint_type: str = "STANDARD",
        pipeline_type: str = "TRIGGERED",
        warehouse_name: Optional[str] = None,
        query_type: str = "ANN",
    ):
        """
        Initialize the Databricks Vector Search vector store.

        Args:
            workspace_url (str): Databricks workspace URL.
            access_token (str, optional): Personal access token for authentication.
            client_id (str, optional): Service principal client ID for authentication.
            client_secret (str, optional): Service principal client secret for authentication.
            azure_client_id (str, optional): Azure AD application client ID (for Azure Databricks).
            azure_client_secret (str, optional): Azure AD application client secret (for Azure Databricks).
            endpoint_name (str): Vector search endpoint name.
            catalog (str): Unity Catalog catalog name.
            schema (str): Unity Catalog schema name.
            table_name (str): Source Delta table name.
            index_name (str, optional): Vector search index name (default: "mem0").
            index_type (str, optional): Index type, either "DELTA_SYNC" or "DIRECT_ACCESS" (default: "DELTA_SYNC").
            embedding_model_endpoint_name (str, optional): Embedding model endpoint for Databricks-computed embeddings.
            embedding_dimension (int, optional): Vector embedding dimensions (default: 1536).
            endpoint_type (str, optional): Endpoint type, either "STANDARD" or "STORAGE_OPTIMIZED" (default: "STANDARD").
            pipeline_type (str, optional): Sync pipeline type, either "TRIGGERED" or "CONTINUOUS" (default: "TRIGGERED").
            warehouse_name (str, optional): Databricks SQL warehouse Name (if using SQL warehouse).
            query_type (str, optional): Query type, either "ANN" or "HYBRID" (default: "ANN").
        """
        # Basic identifiers
        self.workspace_url = workspace_url
        self.endpoint_name = endpoint_name
        self.catalog = catalog
        self.schema = schema
        self.table_name = table_name
        self.fully_qualified_table_name = f"{self.catalog}.{self.schema}.{self.table_name}"
        self.index_name = collection_name
        self.fully_qualified_index_name = f"{self.catalog}.{self.schema}.{self.index_name}"

        # Configuration
        self.index_type = index_type
        self.embedding_model_endpoint_name = embedding_model_endpoint_name
        self.embedding_dimension = embedding_dimension
        self.endpoint_type = endpoint_type
        self.pipeline_type = pipeline_type
        self.query_type = query_type

        # Schema
        self.columns = [
            ColumnInfo(
                name="memory_id",
                type_name=ColumnTypeName.STRING,
                type_text="string",
                type_json='{"type":"string"}',
                nullable=False,
                comment="Primary key",
                position=0,
            ),
            ColumnInfo(
                name="hash",
                type_name=ColumnTypeName.STRING,
                type_text="string",
                type_json='{"type":"string"}',
                comment="Hash of the memory content",
                position=1,
            ),
            ColumnInfo(
                name="agent_id",
                type_name=ColumnTypeName.STRING,
                type_text="string",
                type_json='{"type":"string"}',
                comment="ID of the agent",
                position=2,
            ),
            ColumnInfo(
                name="run_id",
                type_name=ColumnTypeName.STRING,
                type_text="string",
                type_json='{"type":"string"}',
                comment="ID of the run",
                position=3,
            ),
            ColumnInfo(
                name="user_id",
                type_name=ColumnTypeName.STRING,
                type_text="string",
                type_json='{"type":"string"}',
                comment="ID of the user",
                position=4,
            ),
            ColumnInfo(
                name="memory",
                type_name=ColumnTypeName.STRING,
                type_text="string",
                type_json='{"type":"string"}',
                comment="Memory content",
                position=5,
            ),
            ColumnInfo(
                name="metadata",
                type_name=ColumnTypeName.STRING,
                type_text="string",
                type_json='{"type":"string"}',
                comment="Additional metadata",
                position=6,
            ),
            ColumnInfo(
                name="created_at",
                type_name=ColumnTypeName.TIMESTAMP,
                type_text="timestamp",
                type_json='{"type":"timestamp"}',
                comment="Creation timestamp",
                position=7,
            ),
            ColumnInfo(
                name="updated_at",
                type_name=ColumnTypeName.TIMESTAMP,
                type_text="timestamp",
                type_json='{"type":"timestamp"}',
                comment="Last update timestamp",
                position=8,
            ),
        ]
        if self.index_type == VectorIndexType.DIRECT_ACCESS:
            self.columns.append(
                ColumnInfo(
                    name="embedding",
                    type_name=ColumnTypeName.ARRAY,
                    type_text="array<float>",
                    type_json='{"type":"array","element":"float","element_nullable":false}',
                    nullable=True,
                    comment="Embedding vector",
                    position=9,
                )
            )
        self.column_names = [col.name for col in self.columns]

        # Initialize Databricks workspace client
        client_config = {}
        if client_id and client_secret:
            client_config.update(
                {
                    "host": workspace_url,
                    "client_id": client_id,
                    "client_secret": client_secret,
                }
            )
        elif azure_client_id and azure_client_secret:
            client_config.update(
                {
                    "host": workspace_url,
                    "azure_client_id": azure_client_id,
                    "azure_client_secret": azure_client_secret,
                }
            )
        elif access_token:
            client_config.update({"host": workspace_url, "token": access_token})
        else:
            # Try automatic authentication
            client_config["host"] = workspace_url

        try:
            self.client = WorkspaceClient(**client_config)
            logger.info("Initialized Databricks workspace client")
        except Exception as e:
            logger.error(f"Failed to initialize Databricks workspace client: {e}")
            raise

        # Get the warehouse ID by name
        self.warehouse_id = next((w.id for w in self.client.warehouses.list() if w.name == warehouse_name), None)

        # Initialize endpoint (required in Databricks)
        self._ensure_endpoint_exists()

        # Check if index exists and create if needed
        collections = self.list_cols()
        if self.fully_qualified_index_name not in collections:
            self.create_col()

    def _ensure_endpoint_exists(self):
        """Ensure the vector search endpoint exists, create if it doesn't."""
        try:
            self.client.vector_search_endpoints.get_endpoint(endpoint_name=self.endpoint_name)
            logger.info(f"Vector search endpoint '{self.endpoint_name}' already exists")
        except Exception:
            # Endpoint doesn't exist, create it
            try:
                logger.info(f"Creating vector search endpoint '{self.endpoint_name}' with type '{self.endpoint_type}'")
                self.client.vector_search_endpoints.create_endpoint_and_wait(
                    name=self.endpoint_name, endpoint_type=self.endpoint_type
                )
                logger.info(f"Successfully created vector search endpoint '{self.endpoint_name}'")
            except Exception as e:
                logger.error(f"Failed to create vector search endpoint '{self.endpoint_name}': {e}")
                raise

    def _ensure_source_table_exists(self):
        """Ensure the source Delta table exists with the proper schema."""
        check = self.client.tables.exists(self.fully_qualified_table_name)

        if check.table_exists:
            logger.info(f"Source table '{self.fully_qualified_table_name}' already exists")
        else:
            logger.info(f"Source table '{self.fully_qualified_table_name}' does not exist, creating it...")
            self.client.tables.create(
                name=self.table_name,
                catalog_name=self.catalog,
                schema_name=self.schema,
                table_type=TableType.MANAGED,
                data_source_format=DataSourceFormat.DELTA,
                storage_location=None,  # Use default storage location
                columns=self.columns,
                properties={"delta.enableChangeDataFeed": "true"},
            )
            logger.info(f"Successfully created source table '{self.fully_qualified_table_name}'")
            self.client.table_constraints.create(
                full_name_arg="logistics_dev.ai.dev_memory",
                constraint=TableConstraint(
                    primary_key_constraint=PrimaryKeyConstraint(
                        name="pk_dev_memory",  # Name of the primary key constraint
                        child_columns=["memory_id"],  # Columns that make up the primary key
                    )
                ),
            )
            logger.info(
                f"Successfully created primary key constraint on 'memory_id' for table '{self.fully_qualified_table_name}'"
            )

    def create_col(self, name=None, vector_size=None, distance=None):
        """
        Create a new collection (index).

        Args:
            name (str, optional): Index name. If provided, will create a new index using the provided source_table_name.
            vector_size (int, optional): Vector dimension size.
            distance (str, optional): Distance metric (not directly applicable for Databricks).

        Returns:
            The index object.
        """
        # Determine index configuration
        embedding_dims = vector_size or self.embedding_dimension
        embedding_source_columns = [
            EmbeddingSourceColumn(
                name="memory",
                embedding_model_endpoint_name=self.embedding_model_endpoint_name,
            )
        ]

        logger.info(f"Creating vector search index '{self.fully_qualified_index_name}'")

        # First, ensure the source Delta table exists
        self._ensure_source_table_exists()

        if self.index_type not in [VectorIndexType.DELTA_SYNC, VectorIndexType.DIRECT_ACCESS]:
            raise ValueError("index_type must be either 'DELTA_SYNC' or 'DIRECT_ACCESS'")

        try:
            if self.index_type == VectorIndexType.DELTA_SYNC:
                index = self.client.vector_search_indexes.create_index(
                    name=self.fully_qualified_index_name,
                    endpoint_name=self.endpoint_name,
                    primary_key="memory_id",
                    index_type=self.index_type,
                    delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
                        source_table=self.fully_qualified_table_name,
                        pipeline_type=self.pipeline_type,
                        columns_to_sync=self.column_names,
                        embedding_source_columns=embedding_source_columns,
                    ),
                )
                logger.info(
                    f"Successfully created vector search index '{self.fully_qualified_index_name}' with DELTA_SYNC type"
                )
                return index

            elif self.index_type == VectorIndexType.DIRECT_ACCESS:
                index = self.client.vector_search_indexes.create_index(
                    name=self.fully_qualified_index_name,
                    endpoint_name=self.endpoint_name,
                    primary_key="memory_id",
                    index_type=self.index_type,
                    direct_access_index_spec=DirectAccessVectorIndexSpec(
                        embedding_source_columns=embedding_source_columns,
                        embedding_vector_columns=[
                            EmbeddingVectorColumn(name="embedding", embedding_dimension=embedding_dims)
                        ],
                    ),
                )
                logger.info(
                    f"Successfully created vector search index '{self.fully_qualified_index_name}' with DIRECT_ACCESS type"
                )
                return index
        except Exception as e:
            logger.error(f"Error making index_type: {self.index_type} for index {self.fully_qualified_index_name}: {e}")

    def _format_sql_value(self, v):
        """
        Format a Python value into a safe SQL literal for Databricks.
        """
        if v is None:
            return "NULL"
        if isinstance(v, bool):
            return "TRUE" if v else "FALSE"
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, (datetime, date)):
            return f"'{v.isoformat()}'"
        if isinstance(v, list):
            # Render arrays (assume numeric or string elements)
            elems = []
            for x in v:
                if x is None:
                    elems.append("NULL")
                elif isinstance(x, (int, float)):
                    elems.append(str(x))
                else:
                    s = str(x).replace("'", "''")
                    elems.append(f"'{s}'")
            return f"array({', '.join(elems)})"
        if isinstance(v, dict):
            try:
                s = json.dumps(v)
            except Exception:
                s = str(v)
            s = s.replace("'", "''")
            return f"'{s}'"
        # Fallback: treat as string
        s = str(v).replace("'", "''")
        return f"'{s}'"

    def insert(self, vectors: list, payloads: list = None, ids: list = None):
        """
        Insert vectors into the index.

        Args:
            vectors (List[List[float]]): List of vectors to insert.
            payloads (List[Dict], optional): List of payloads corresponding to vectors.
            ids (List[str], optional): List of IDs corresponding to vectors.
        """
        # Determine the number of items to process
        num_items = len(payloads) if payloads else len(vectors) if vectors else 0

        value_tuples = []
        for i in range(num_items):
            values = []
            for col in self.columns:
                if col.name == "memory_id":
                    val = ids[i] if ids and i < len(ids) else str(uuid.uuid4())
                elif col.name == "embedding":
                    val = vectors[i] if vectors and i < len(vectors) else []
                elif col.name == "memory":
                    val = payloads[i].get("data") if payloads and i < len(payloads) else None
                else:
                    val = payloads[i].get(col.name) if payloads and i < len(payloads) else None
                values.append(val)
            formatted = [self._format_sql_value(v) for v in values]
            value_tuples.append(f"({', '.join(formatted)})")

        insert_sql = f"INSERT INTO {self.fully_qualified_table_name} ({', '.join(self.column_names)}) VALUES {', '.join(value_tuples)}"

        # Execute the insert
        try:
            response = self.client.statement_execution.execute_statement(
                statement=insert_sql, warehouse_id=self.warehouse_id, wait_timeout="30s"
            )
            if response.status.state.value == "SUCCEEDED":
                logger.info(
                    f"Successfully inserted {num_items} items into Delta table {self.fully_qualified_table_name}"
                )
                return
            else:
                logger.error(f"Failed to insert items: {response.status.error}")
                raise Exception(f"Insert operation failed: {response.status.error}")
        except Exception as e:
            logger.error(f"Insert operation failed: {e}")
            raise

    def search(self, query: str, vectors: list, limit: int = 5, filters: dict = None) -> List[MemoryResult]:
        """
        Search for similar vectors or text using the Databricks Vector Search index.

        Args:
            query (str): Search query text (for text-based search).
            vectors (list): Query vector (for vector-based search).
            limit (int): Maximum number of results.
            filters (dict): Filters to apply.

        Returns:
            List of MemoryResult objects.
        """
        try:
            filters_json = json.dumps(filters) if filters else None

            # Choose query type
            if self.index_type == VectorIndexType.DELTA_SYNC and query:
                # Text-based search
                sdk_results = self.client.vector_search_indexes.query_index(
                    index_name=self.fully_qualified_index_name,
                    columns=self.column_names,
                    query_text=query,
                    num_results=limit,
                    query_type=self.query_type,
                    filters_json=filters_json,
                )
            elif self.index_type == VectorIndexType.DIRECT_ACCESS and vectors:
                # Vector-based search
                sdk_results = self.client.vector_search_indexes.query_index(
                    index_name=self.fully_qualified_index_name,
                    columns=self.column_names,
                    query_vector=vectors,
                    num_results=limit,
                    query_type=self.query_type,
                    filters_json=filters_json,
                )
            else:
                raise ValueError("Must provide query text for DELTA_SYNC or vectors for DIRECT_ACCESS.")

            # Parse results
            result_data = sdk_results.result if hasattr(sdk_results, "result") else sdk_results
            data_array = result_data.data_array if getattr(result_data, "data_array", None) else []

            memory_results = []
            for row in data_array:
                # Map columns to values
                row_dict = dict(zip(self.column_names, row)) if isinstance(row, (list, tuple)) else row
                score = row_dict.get("score") or (
                    row[-1] if isinstance(row, (list, tuple)) and len(row) > len(self.column_names) else None
                )
                payload = {k: row_dict.get(k) for k in self.column_names}
                payload["data"] = payload.get("memory", "")
                memory_id = row_dict.get("memory_id") or row_dict.get("id")
                memory_results.append(MemoryResult(id=memory_id, score=score, payload=payload))
            return memory_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def delete(self, vector_id):
        """
        Delete a vector by ID from the Delta table.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        try:
            logger.info(f"Deleting vector with ID {vector_id} from Delta table {self.fully_qualified_table_name}")

            delete_sql = f"DELETE FROM {self.fully_qualified_table_name} WHERE memory_id = '{vector_id}'"

            response = self.client.statement_execution.execute_statement(
                statement=delete_sql, warehouse_id=self.warehouse_id, wait_timeout="30s"
            )

            if response.status.state.value == "SUCCEEDED":
                logger.info(f"Successfully deleted vector with ID {vector_id}")
            else:
                logger.error(f"Failed to delete vector with ID {vector_id}: {response.status.error}")

        except Exception as e:
            logger.error(f"Delete operation failed for vector ID {vector_id}: {e}")
            raise

    def update(self, vector_id=None, vector=None, payload=None):
        """
        Update a vector and its payload in the Delta table.

        Args:
            vector_id (str): ID of the vector to update.
            vector (list, optional): New vector values.
            payload (dict, optional): New payload data.
        """

        update_sql = f"UPDATE {self.fully_qualified_table_name} SET "
        set_clauses = []
        if not vector_id:
            logger.error("vector_id is required for update operation")
            return
        if vector is not None:
            if not isinstance(vector, list):
                logger.error("vector must be a list of float values")
                return
            set_clauses.append(f"embedding = {vector}")
        if payload:
            if not isinstance(payload, dict):
                logger.error("payload must be a dictionary")
                return
            for key, value in payload.items():
                if key not in excluded_keys:
                    set_clauses.append(f"{key} = '{value}'")

        if not set_clauses:
            logger.error("No fields to update")
            return
        update_sql += ", ".join(set_clauses)
        update_sql += f" WHERE memory_id = '{vector_id}'"
        try:
            logger.info(f"Updating vector with ID {vector_id} in Delta table {self.fully_qualified_table_name}")

            response = self.client.statement_execution.execute_statement(
                statement=update_sql, warehouse_id=self.warehouse_id, wait_timeout="30s"
            )

            if response.status.state.value == "SUCCEEDED":
                logger.info(f"Successfully updated vector with ID {vector_id}")
            else:
                logger.error(f"Failed to update vector with ID {vector_id}: {response.status.error}")
        except Exception as e:
            logger.error(f"Update operation failed for vector ID {vector_id}: {e}")
            raise

    def get(self, vector_id) -> MemoryResult:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            MemoryResult: The retrieved vector.
        """
        try:
            # Use query with ID filter to retrieve the specific vector
            filters = {"memory_id": vector_id}
            filters_json = json.dumps(filters)

            results = self.client.vector_search_indexes.query_index(
                index_name=self.fully_qualified_index_name,
                columns=self.column_names,
                query_text=" ",  # Empty query, rely on filters
                num_results=1,
                query_type=self.query_type,
                filters_json=filters_json,
            )

            # Process results
            result_data = results.result if hasattr(results, "result") else results
            data_array = result_data.data_array if hasattr(result_data, "data_array") else []

            if not data_array:
                raise KeyError(f"Vector with ID {vector_id} not found")

            result = data_array[0]
            row_data = result if isinstance(result, dict) else result.__dict__

            # Build payload following the standard schema
            payload = {
                "hash": row_data.get("hash", "unknown"),
                "data": row_data.get("memory", row_data.get("data", "unknown")),
                "created_at": row_data.get("created_at"),
            }

            # Add updated_at if available
            if "updated_at" in row_data:
                payload["updated_at"] = row_data.get("updated_at")

            # Add optional fields
            for field in ["agent_id", "run_id", "user_id"]:
                if field in row_data:
                    payload[field] = row_data[field]

            # Add metadata
            if "metadata" in row_data:
                try:
                    metadata = json.loads(extract_json(row_data["metadata"]))
                    payload.update(metadata)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"Failed to parse metadata: {row_data.get('metadata')}")

            memory_id = row_data.get("memory_id", row_data.get("memory_id", vector_id))
            return MemoryResult(id=memory_id, payload=payload)

        except Exception as e:
            logger.error(f"Failed to get vector with ID {vector_id}: {e}")
            raise

    def list_cols(self) -> List[str]:
        """
        List all collections (indexes).

        Returns:
            List of index names.
        """
        try:
            indexes = self.client.vector_search_indexes.list_indexes(endpoint_name=self.endpoint_name)
            return [idx.name for idx in indexes]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            raise

    def delete_col(self):
        """
        Delete the current collection (index).
        """
        try:
            # Try fully qualified first
            try:
                self.client.vector_search_indexes.delete_index(index_name=self.fully_qualified_index_name)
                logger.info(f"Successfully deleted index '{self.fully_qualified_index_name}'")
            except Exception:
                self.client.vector_search_indexes.delete_index(index_name=self.index_name)
                logger.info(f"Successfully deleted index '{self.index_name}' (short name)")
        except Exception as e:
            logger.error(f"Failed to delete index '{self.index_name}': {e}")
            raise

    def col_info(self, name=None):
        """
        Get information about a collection (index).

        Args:
            name (str, optional): Index name. Defaults to current index.

        Returns:
            Dict: Index information.
        """
        try:
            index_name = name or self.index_name
            index = self.client.vector_search_indexes.get_index(index_name=index_name)
            return {"name": index.name, "fields": self.columns}
        except Exception as e:
            logger.error(f"Failed to get info for index '{name or self.index_name}': {e}")
            raise

    def list(self, filters: dict = None, limit: int = None) -> list[MemoryResult]:
        """
        List all recent created memories from the vector store.

        Args:
            filters (dict, optional): Filters to apply.
            limit (int, optional): Maximum number of results.

        Returns:
            List containing list of MemoryResult objects.
        """
        try:
            filters_json = json.dumps(filters) if filters else None
            num_results = limit or 100
            columns = self.column_names
            sdk_results = self.client.vector_search_indexes.query_index(
                index_name=self.fully_qualified_index_name,
                columns=columns,
                query_text=" ",
                num_results=num_results,
                query_type=self.query_type,
                filters_json=filters_json,
            )
            result_data = sdk_results.result if hasattr(sdk_results, "result") else sdk_results
            data_array = result_data.data_array if hasattr(result_data, "data_array") else []

            memory_results = []
            for row in data_array:
                row_dict = dict(zip(columns, row)) if isinstance(row, (list, tuple)) else row
                payload = {k: row_dict.get(k) for k in columns}
                # Parse metadata if present
                if "metadata" in payload and payload["metadata"]:
                    try:
                        payload.update(json.loads(payload["metadata"]))
                    except Exception:
                        pass
                memory_id = row_dict.get("memory_id") or row_dict.get("id")
                memory_results.append(MemoryResult(id=memory_id, payload=payload))
            return [memory_results]
        except Exception as e:
            logger.error(f"Failed to list memories: {e}")
            return []

    def reset(self):
        """Reset the vector search index and underlying source table.

        This will attempt to delete the existing index (both fully qualified and short name forms
        for robustness), drop the backing Delta table, recreate the table with the expected schema,
        and finally recreate the index. Use with caution as all existing data will be removed.
        """
        fq_index = self.fully_qualified_index_name
        logger.warning(f"Resetting Databricks vector search index '{fq_index}'...")
        try:
            # Try deleting via fully qualified name first
            try:
                self.client.vector_search_indexes.delete_index(index_name=fq_index)
                logger.info(f"Deleted index '{fq_index}'")
            except Exception as e_fq:
                logger.debug(f"Failed deleting fully qualified index name '{fq_index}': {e_fq}. Trying short name...")
                try:
                    # Fallback to existing helper which may use short name
                    self.delete_col()
                except Exception as e_short:
                    logger.debug(f"Failed deleting short index name '{self.index_name}': {e_short}")

            # Drop the backing table (if it exists)
            try:
                drop_sql = f"DROP TABLE IF EXISTS {self.fully_qualified_table_name}"
                resp = self.client.statement_execution.execute_statement(
                    statement=drop_sql, warehouse_id=self.warehouse_id, wait_timeout="30s"
                )
                if getattr(resp.status, "state", None) == "SUCCEEDED":
                    logger.info(f"Dropped table '{self.fully_qualified_table_name}'")
                else:
                    logger.warning(
                        f"Attempted to drop table '{self.fully_qualified_table_name}' but state was {getattr(resp.status, 'state', 'UNKNOWN')}: {getattr(resp.status, 'error', None)}"
                    )
            except Exception as e_drop:
                logger.warning(f"Failed to drop table '{self.fully_qualified_table_name}': {e_drop}")

            # Recreate table & index
            self._ensure_source_table_exists()
            self.create_col()
            logger.info(f"Successfully reset index '{fq_index}'")
        except Exception as e:
            logger.error(f"Error resetting index '{fq_index}': {e}")
            raise
