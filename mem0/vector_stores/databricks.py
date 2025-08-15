import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, List

import numpy as np
import pytz
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.catalog import ColumnInfo, ColumnTypeName, TableInfo
from databricks.sdk.service.sql import StatementExecutionAPI
from databricks.sdk.service.vectorsearch import (
    VectorIndexType,
    DeltaSyncVectorIndexSpecRequest,
    DirectAccessVectorIndexSpec,
    EmbeddingSourceColumn,
    PipelineType
)

from mem0.memory.utils import extract_json
from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

# Standard schema fields matching other vector stores
DEFAULT_SCHEMA_FIELDS = [
    "memory_id",
    "hash", 
    "agent_id",
    "run_id",
    "user_id",
    "memory",
    "metadata",
    "created_at",
    "updated_at"
]

excluded_keys = {"user_id", "agent_id", "run_id", "hash", "data", "created_at", "updated_at"}


class MemoryResult:
    def __init__(self, id: str, payload: dict, score: float = None):
        self.id = id
        self.payload = payload
        self.score = score


class Databricks(VectorStoreBase):
    def __init__(
        self,
        workspace_url: str,
        access_token: Optional[str] = None,
        service_principal_client_id: Optional[str] = None,
        service_principal_client_secret: Optional[str] = None,
        endpoint_name: str = None,
        index_name: str = None,
        source_table_name: str = None,
        primary_key: str = "id",
        embedding_vector_column: str = "embedding",
        embedding_source_column: Optional[str] = None,
        embedding_model_endpoint_name: Optional[str] = None,
        embedding_dimension: int = 1536,
        endpoint_type: str = "STANDARD", 
        pipeline_type: str = "TRIGGERED",
        collection_name: str = "mem0",
    ):
        """
        Initialize the Databricks Vector Search vector store.

        Args:
            workspace_url (str): Databricks workspace URL.
            access_token (str, optional): Personal access token.
            service_principal_client_id (str, optional): Service principal client ID.
            service_principal_client_secret (str, optional): Service principal client secret.
            endpoint_name (str): Vector search endpoint name.
            index_name (str): Vector search index name.
            source_table_name (str): Source Delta table name.
            primary_key (str): Primary key column name.
            embedding_vector_column (str): Embedding vector column name.
            embedding_source_column (str, optional): Text column for embeddings.
            embedding_model_endpoint_name (str, optional): Embedding model endpoint.
            embedding_dimension (int): Vector embedding dimensions.
            endpoint_type (str): Endpoint type (STANDARD or STORAGE_OPTIMIZED).
            pipeline_type (str): Pipeline type (TRIGGERED or CONTINUOUS).
            collection_name (str): Collection name.
        """
        self.workspace_url = workspace_url
        self.endpoint_name = endpoint_name
        self.index_name = index_name
        self.source_table_name = source_table_name
        self.primary_key = primary_key
        self.embedding_vector_column = embedding_vector_column
        self.embedding_source_column = embedding_source_column
        self.embedding_model_endpoint_name = embedding_model_endpoint_name
        self.embedding_dimension = embedding_dimension
        self.endpoint_type = endpoint_type
        self.pipeline_type = pipeline_type
        self.collection_name = collection_name

        # Initialize Databricks workspace client
        client_config = {}
        if service_principal_client_id and service_principal_client_secret:
            client_config.update({
                "host": workspace_url,
                "client_id": service_principal_client_id,
                "client_secret": service_principal_client_secret
            })
        elif access_token:
            client_config.update({
                "host": workspace_url,
                "token": access_token
            })
        else:
            # Try automatic authentication
            client_config["host"] = workspace_url
        
        try:
            self.client = WorkspaceClient(**client_config)
            logger.info("Initialized Databricks workspace client")
        except Exception as e:
            logger.error(f"Failed to initialize Databricks workspace client: {e}")
            raise

        # Initialize endpoint (required in Databricks)
        self._ensure_endpoint_exists()
        
        # Check if index exists and create if needed
        collections = self.list_cols()
        if self.index_name not in collections:
            self.create_col()

    def _ensure_endpoint_exists(self):
        """Ensure the vector search endpoint exists, create if it doesn't."""
        try:
            # Check if endpoint exists using the new SDK
            self.client.vector_search_endpoints.get_endpoint(name=self.endpoint_name)
            logger.info(f"Vector search endpoint '{self.endpoint_name}' already exists")
        except Exception:
            # Endpoint doesn't exist, create it
            try:
                logger.info(f"Creating vector search endpoint '{self.endpoint_name}' with type '{self.endpoint_type}'")
                self.client.vector_search_endpoints.create_endpoint(
                    name=self.endpoint_name,
                    endpoint_type=self.endpoint_type
                )
                logger.info(f"Successfully created vector search endpoint '{self.endpoint_name}'")
            except Exception as e:
                logger.error(f"Failed to create vector search endpoint '{self.endpoint_name}': {e}")
                raise



    def _ensure_source_table_exists(self, table_name=None):
        """Ensure the source Delta table exists with the proper schema."""
        source_table = table_name or self.source_table_name
        
        try:
            # Check if table exists using workspace client
            catalog_name, schema_name, table_name_only = source_table.split('.')
            
            try:
                # Try to get table info
                self.client.tables.get(f"{catalog_name}.{schema_name}.{table_name_only}")
                logger.info(f"Source table '{source_table}' already exists")
                return
            except Exception:
                logger.info(f"Source table '{source_table}' does not exist, creating it...")
                
            # Create the table using SQL
            if self.embedding_source_column and self.embedding_model_endpoint_name:
                # Table for Databricks-computed embeddings
                create_table_sql = f"""
                CREATE TABLE {source_table} (
                    {self.primary_key} STRING NOT NULL,
                    memory_id STRING,
                    hash STRING,
                    agent_id STRING,
                    run_id STRING,
                    user_id STRING,
                    memory STRING,
                    metadata STRING,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    {self.embedding_source_column} STRING
                ) USING DELTA
                TBLPROPERTIES (
                    'delta.enableChangeDataFeed' = 'true'
                )
                """
            else:
                # Table for self-managed embeddings
                create_table_sql = f"""
                CREATE TABLE {source_table} (
                    {self.primary_key} STRING NOT NULL,
                    memory_id STRING,
                    hash STRING,
                    agent_id STRING,
                    run_id STRING,
                    user_id STRING,
                    memory STRING,
                    metadata STRING,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    {self.embedding_vector_column} ARRAY<FLOAT>
                ) USING DELTA
                TBLPROPERTIES (
                    'delta.enableChangeDataFeed' = 'true'
                )
                """
            
            # Execute the CREATE TABLE statement
            response = self.client.statement_execution.execute_statement(
                statement=create_table_sql,
                warehouse_id=None,  # Use default warehouse
                wait_timeout="30s"
            )
            
            if response.status.state == "SUCCEEDED":
                logger.info(f"Successfully created source table '{source_table}'")
            else:
                error_msg = f"Failed to create source table '{source_table}': {response.status.error}"
                logger.error(error_msg)
                raise ValueError(error_msg)
                
        except Exception as e:
            logger.error(f"Error ensuring source table exists: {e}")
            raise

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
        if name:
            # Creating a new named index
            index_name = name
            source_table = self.source_table_name
            embedding_dims = vector_size or self.embedding_dimension
        else:
            # Creating the default index
            index_name = self.index_name
            source_table = self.source_table_name
            embedding_dims = vector_size or self.embedding_dimension
        
        try:
            logger.info(f"Creating vector search index '{index_name}'")
            
            # First, ensure the source Delta table exists
            self._ensure_source_table_exists(source_table)
            
            if self.embedding_source_column and self.embedding_model_endpoint_name:
                # Databricks will compute embeddings
                delta_sync_spec = DeltaSyncVectorIndexSpecRequest(
                    source_table=source_table,
                    pipeline_type=PipelineType.CONTINUOUS if self.pipeline_type == "CONTINUOUS" else PipelineType.TRIGGERED,
                    embedding_source_columns=[
                        EmbeddingSourceColumn(
                            name=self.embedding_source_column,
                            embedding_model_endpoint_name=self.embedding_model_endpoint_name
                        )
                    ]
                )
            else:
                # Self-managed embeddings
                delta_sync_spec = DeltaSyncVectorIndexSpecRequest(
                    source_table=source_table,
                    pipeline_type=PipelineType.CONTINUOUS if self.pipeline_type == "CONTINUOUS" else PipelineType.TRIGGERED,
                    embedding_dimension=embedding_dims,
                    embedding_vector_columns=[{"name": self.embedding_vector_column}]
                )
            
            # Create the index
            index = self.client.vector_search_indexes.create_index(
                name=index_name,
                endpoint_name=self.endpoint_name,
                primary_key=self.primary_key,
                index_type=VectorIndexType.DELTA_SYNC,
                delta_sync_index_spec=delta_sync_spec
            )
            
            # If creating the default index, store it as instance variable
            if not name:
                self.index = index
            
            logger.info(f"Successfully created vector search index '{index_name}'")
            
        except Exception as e:
            logger.error(f"Failed to create vector search index '{index_name}': {e}")
            raise

    def insert(self, vectors: list, payloads: list = None, ids: list = None):
        """
        Insert vectors into the Delta table (will sync to index).
        
        Args:
            vectors (list): List of vectors to insert.
            payloads (list, optional): List of payloads corresponding to vectors.
            ids (list, optional): List of IDs corresponding to vectors.
        """
        try:
            if not vectors:
                logger.warning("No vectors provided for insertion")
                return
                
            logger.info(f"Inserting {len(vectors)} vectors into Delta table {self.source_table_name}")
            
            # Prepare data for insertion
            current_time = datetime.now(pytz.timezone("UTC")).isoformat()
            
            for i, vector in enumerate(vectors):
                # Generate ID if not provided
                record_id = ids[i] if ids and i < len(ids) else str(uuid.uuid4())
                payload = payloads[i] if payloads and i < len(payloads) else {}
                
                # Extract required fields from payload
                memory_id = payload.get("memory_id", str(uuid.uuid4()))
                hash_value = payload.get("hash", "")
                agent_id = payload.get("agent_id", "")
                run_id = payload.get("run_id", "")
                user_id = payload.get("user_id", "")
                memory_text = payload.get("data", payload.get("memory", ""))
                
                # Handle metadata
                metadata_dict = {}
                for key, value in payload.items():
                    if key not in excluded_keys:
                        metadata_dict[key] = value
                metadata_json = json.dumps(metadata_dict) if metadata_dict else "{}"
                
                # Prepare SQL based on embedding type
                if self.embedding_source_column and self.embedding_model_endpoint_name:
                    # For Databricks-computed embeddings (no vector column)
                    insert_sql = f"""
                    INSERT INTO {self.source_table_name} VALUES (
                        '{record_id}',
                        '{memory_id}',
                        '{hash_value}',
                        '{agent_id}',
                        '{run_id}',
                        '{user_id}',
                        '{memory_text.replace("'", "''")}',
                        '{metadata_json.replace("'", "''")}',
                        '{current_time}',
                        '{current_time}',
                        '{memory_text.replace("'", "''")}'
                    )
                    """
                else:
                    # For self-managed embeddings (with vector column)
                    insert_sql = f"""
                    INSERT INTO {self.source_table_name} VALUES (
                        '{record_id}',
                        '{memory_id}',
                        '{hash_value}',
                        '{agent_id}',
                        '{run_id}',
                        '{user_id}',
                        '{memory_text.replace("'", "''")}',
                        '{metadata_json.replace("'", "''")}',
                        '{current_time}',
                        '{current_time}',
                        array({','.join(map(str, vector))})
                    )
                    """
                
                # Execute the insert
                response = self.client.statement_execution.execute_statement(
                    statement=insert_sql,
                    warehouse_id=None,
                    wait_timeout="30s"
                )
                
                if response.status.state != "SUCCEEDED":
                    logger.error(f"Failed to insert vector {i}: {response.status.error}")
                    
            logger.info(f"Successfully inserted {len(vectors)} vectors into Delta table")
            
        except Exception as e:
            logger.error(f"Insert operation failed: {e}")
            raise

    def search(self, query: str, vectors: list, limit: int = 5, filters: dict = None):
        """
        Search for similar vectors.
        
        Args:
            query (str): Search query text.
            vectors (list): Query vector.
            limit (int): Maximum number of results.
            filters (dict): Filters to apply.
        
        Returns:
            List of MemoryResult objects.
        """
        try:
            # Prepare filters for Databricks
            filters_json = None
            if filters:
                # Convert filters to JSON string format for the new SDK
                import json
                filters_json = json.dumps(filters)

            # Perform vector search using the new SDK
            if self.embedding_source_column and query:
                # Text-based search (Databricks computes embeddings)
                results = self.client.vector_search_indexes.query_index(
                    index_name=self.index_name,
                    columns=["*"],  # Get all columns
                    query_text=query,
                    num_results=limit,
                    filters_json=filters_json
                )
            else:
                # Vector-based search (self-managed embeddings) 
                results = self.client.vector_search_indexes.query_index(
                    index_name=self.index_name,
                    columns=["*"],  # Get all columns
                    query_vector=vectors,
                    num_results=limit,
                    filters_json=filters_json
                )

            # Convert results to MemoryResult format
            memory_results = []
            # The new SDK returns results in a different format
            result_data = results.result if hasattr(results, 'result') else results
            data_array = result_data.data_array if hasattr(result_data, 'data_array') else []
            
            for result in data_array:
                # Extract metadata and score
                score = result.get("score") if isinstance(result, dict) else getattr(result, 'score', None)
                row_data = result if isinstance(result, dict) else result.__dict__
                
                # Build payload following the standard schema
                payload = {
                    "hash": row_data.get("hash", "unknown"),
                    "data": row_data.get("memory", row_data.get("data", "unknown")),
                    "created_at": self._format_timestamp(row_data.get("created_at")),
                }
                
                # Add updated_at if available
                if "updated_at" in row_data:
                    payload["updated_at"] = self._format_timestamp(row_data.get("updated_at"))
                
                # Add optional fields
                for field in ["agent_id", "run_id", "user_id"]:
                    if field in row_data:
                        payload[field] = row_data[field]
                
                # Add metadata
                if "metadata" in row_data:
                    try:
                        metadata = json.loads(extract_json(str(row_data["metadata"])))
                        payload.update(metadata)
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(f"Failed to parse metadata: {row_data.get('metadata')}")
                
                memory_id = row_data.get("memory_id", row_data.get(self.primary_key, "unknown"))
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
            logger.info(f"Deleting vector with ID {vector_id} from Delta table {self.source_table_name}")
            
            delete_sql = f"""
            DELETE FROM {self.source_table_name} 
            WHERE {self.primary_key} = '{vector_id}'
            """
            
            response = self.client.statement_execution.execute_statement(
                statement=delete_sql,
                warehouse_id=None,
                wait_timeout="30s"
            )
            
            if response.status.state == "SUCCEEDED":
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
        try:
            if not vector_id:
                logger.error("vector_id is required for update operation")
                return
                
            logger.info(f"Updating vector with ID {vector_id} in Delta table {self.source_table_name}")
            
            # Build SET clause based on what needs to be updated
            set_clauses = []
            current_time = datetime.now(pytz.timezone("UTC")).isoformat()
            set_clauses.append(f"updated_at = '{current_time}'")
            
            if payload:
                # Extract fields from payload
                if "memory" in payload or "data" in payload:
                    memory_text = payload.get("data", payload.get("memory", ""))
                    escaped_memory = memory_text.replace("'", "''")
                    set_clauses.append(f"memory = '{escaped_memory}'")
                    
                if "hash" in payload:
                    set_clauses.append(f"hash = '{payload['hash']}'")
                    
                if "agent_id" in payload:
                    set_clauses.append(f"agent_id = '{payload['agent_id']}'")
                    
                if "run_id" in payload:
                    set_clauses.append(f"run_id = '{payload['run_id']}'")
                    
                if "user_id" in payload:
                    set_clauses.append(f"user_id = '{payload['user_id']}'")
                
                # Handle metadata
                metadata_dict = {}
                for key, value in payload.items():
                    if key not in excluded_keys:
                        metadata_dict[key] = value
                if metadata_dict:
                    metadata_json = json.dumps(metadata_dict)
                    escaped_metadata = metadata_json.replace("'", "''")
                    set_clauses.append(f"metadata = '{escaped_metadata}'")
            
            if vector and not (self.embedding_source_column and self.embedding_model_endpoint_name):
                # Update vector for self-managed embeddings
                vector_array = f"array({','.join(map(str, vector))})"
                set_clauses.append(f"{self.embedding_vector_column} = {vector_array}")
            
            if len(set_clauses) <= 1:  # Only updated_at
                logger.warning("No fields to update")
                return
            
            update_sql = f"""
            UPDATE {self.source_table_name} 
            SET {', '.join(set_clauses)}
            WHERE {self.primary_key} = '{vector_id}'
            """
            
            response = self.client.statement_execution.execute_statement(
                statement=update_sql,
                warehouse_id=None,
                wait_timeout="30s"
            )
            
            if response.status.state == "SUCCEEDED":
                logger.info(f"Successfully updated vector with ID {vector_id}")
            else:
                logger.error(f"Failed to update vector with ID {vector_id}: {response.status.error}")
                
        except Exception as e:
            logger.error(f"Update operation failed for vector ID {vector_id}: {e}")
            raise

    def get(self, vector_id):
        """
        Retrieve a vector by ID.
        
        Args:
            vector_id (str): ID of the vector to retrieve.
        
        Returns:
            MemoryResult: The retrieved vector.
        """
        try:
            # Use query with ID filter to retrieve the specific vector
            filters = {self.primary_key: vector_id}
            filters_json = json.dumps(filters)
            
            results = self.client.vector_search_indexes.query_index(
                index_name=self.index_name,
                columns=["*"],  # Get all columns
                query_text="",  # Empty query, rely on filters
                num_results=1,
                filters_json=filters_json
            )
            
            # Process results
            result_data = results.result if hasattr(results, 'result') else results
            data_array = result_data.data_array if hasattr(result_data, 'data_array') else []
            
            if not data_array:
                raise KeyError(f"Vector with ID {vector_id} not found")
            
            result = data_array[0]
            row_data = result if isinstance(result, dict) else result.__dict__
            
            # Build payload following the standard schema
            payload = {
                "hash": row_data.get("hash", "unknown"),
                "data": row_data.get("memory", row_data.get("data", "unknown")),
                "created_at": self._format_timestamp(row_data.get("created_at")),
            }
            
            # Add updated_at if available
            if "updated_at" in row_data:
                payload["updated_at"] = self._format_timestamp(row_data.get("updated_at"))
            
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
            
            memory_id = row_data.get("memory_id", row_data.get(self.primary_key, vector_id))
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
            self.client.vector_search_indexes.delete_index(index_name=self.index_name)
            logger.info(f"Successfully deleted index '{self.index_name}'")
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
            return index.__dict__ if hasattr(index, '__dict__') else index
        except Exception as e:
            logger.error(f"Failed to get info for index '{name or self.index_name}': {e}")
            raise

    def list(self, filters: dict = None, limit: int = None) -> list:
        """
        List all recent created memories from the vector store.
        
        Args:
            filters (dict, optional): Filters to apply.
            limit (int, optional): Maximum number of results.
        
        Returns:
            List containing list of MemoryResult objects.
        """
        try:
            # Use empty query to get all results, sorted by created_at
            filters_json = None
            if filters:
                # Convert filters to JSON string format for the new SDK
                filters_json = json.dumps(filters)

            # Get results using the new SDK
            num_results = limit or 100  # Default limit
            results = self.client.vector_search_indexes.query_index(
                index_name=self.index_name,
                columns=["*"],  # Get all columns
                query_text="",  # Empty query to get all
                num_results=num_results,
                filters_json=filters_json
            )

            # Convert results to MemoryResult format
            memory_results = []
            result_data = results.result if hasattr(results, 'result') else results
            data_array = result_data.data_array if hasattr(result_data, 'data_array') else []
            
            for result in data_array:
                row_data = result if isinstance(result, dict) else result.__dict__
                
                # Build payload following the standard schema
                payload = {
                    "hash": row_data.get("hash", "unknown"),
                    "data": row_data.get("memory", row_data.get("data", "unknown")),
                    "created_at": self._format_timestamp(row_data.get("created_at")),
                }
                
                # Add updated_at if available
                if "updated_at" in row_data:
                    payload["updated_at"] = self._format_timestamp(row_data.get("updated_at"))
                
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
                
                memory_id = row_data.get("memory_id", row_data.get(self.primary_key, "unknown"))
                memory_results.append(MemoryResult(id=memory_id, payload=payload))
            
            return [memory_results]  # Return as nested list to match interface
            
        except Exception as e:
            logger.error(f"Failed to list memories: {e}")
            return [[]]  # Return empty nested list on error

    def reset(self):
        """
        Reset the index by deleting and recreating it.
        """
        try:
            logger.warning(f"Resetting index {self.index_name}...")
            
            # Delete the current index
            self.delete_col()
            
            # Recreate the index
            self.create_col()
            
            logger.info(f"Successfully reset index {self.index_name}")
            
        except Exception as e:
            logger.error(f"Failed to reset index {self.index_name}: {e}")
            raise

    def _format_timestamp(self, timestamp):
        """
        Format a timestamp to ISO format.
        
        Args:
            timestamp: Timestamp to format (int, float, or string).
        
        Returns:
            str: Formatted timestamp string.
        """
        if timestamp is None:
            return datetime.now(pytz.timezone("UTC")).isoformat(timespec="microseconds")
        
        try:
            if isinstance(timestamp, (int, float)):
                # Unix timestamp
                dt = datetime.fromtimestamp(timestamp, tz=pytz.timezone("UTC"))
                return dt.isoformat(timespec="microseconds")
            elif isinstance(timestamp, str):
                # Try to parse as ISO format first
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    return dt.isoformat(timespec="microseconds")
                except ValueError:
                    # Try as unix timestamp string
                    dt = datetime.fromtimestamp(float(timestamp), tz=pytz.timezone("UTC"))
                    return dt.isoformat(timespec="microseconds")
            else:
                # Fallback to current time
                return datetime.now(pytz.timezone("UTC")).isoformat(timespec="microseconds")
        except (ValueError, TypeError):
            # Fallback to current time on any parsing error
            return datetime.now(pytz.timezone("UTC")).isoformat(timespec="microseconds")
