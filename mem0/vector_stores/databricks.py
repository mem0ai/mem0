import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pytz
from databricks.vector_search.client import VectorSearchClient

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


class DatabricksDB(VectorStoreBase):
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

        # Initialize the Databricks Vector Search client
        try:
            if service_principal_client_id and service_principal_client_secret:
                # Use service principal authentication (recommended for production)
                self.client = VectorSearchClient(
                    workspace_url=workspace_url,
                    service_principal_client_id=service_principal_client_id,
                    service_principal_client_secret=service_principal_client_secret
                )
                logger.info("Initialized Databricks Vector Search client with service principal authentication")
            elif access_token:
                # Use personal access token
                self.client = VectorSearchClient(
                    workspace_url=workspace_url,
                    personal_access_token=access_token
                )
                logger.info("Initialized Databricks Vector Search client with personal access token")
            else:
                # Try automatic authentication (e.g., in notebook environment)
                self.client = VectorSearchClient()
                logger.info("Initialized Databricks Vector Search client with automatic authentication")
        except Exception as e:
            logger.error(f"Failed to initialize Databricks Vector Search client: {e}")
            raise

        # Initialize endpoint and index
        self._ensure_endpoint_exists()
        self._ensure_index_exists()

    def _ensure_endpoint_exists(self):
        """Ensure the vector search endpoint exists, create if it doesn't."""
        try:
            # Check if endpoint exists
            self.client.get_endpoint(self.endpoint_name)
            logger.info(f"Vector search endpoint '{self.endpoint_name}' already exists")
        except Exception:
            # Endpoint doesn't exist, create it
            try:
                logger.info(f"Creating vector search endpoint '{self.endpoint_name}' with type '{self.endpoint_type}'")
                self.client.create_endpoint(
                    name=self.endpoint_name,
                    endpoint_type=self.endpoint_type
                )
                logger.info(f"Successfully created vector search endpoint '{self.endpoint_name}'")
            except Exception as e:
                logger.error(f"Failed to create vector search endpoint '{self.endpoint_name}': {e}")
                raise

    def _ensure_index_exists(self):
        """Ensure the vector search index exists, create if it doesn't."""
        try:
            # Try to get the index
            self.index = self.client.get_index(self.index_name)
            logger.info(f"Vector search index '{self.index_name}' already exists")
        except Exception:
            # Index doesn't exist, create it
            try:
                logger.info(f"Creating vector search index '{self.index_name}'")
                
                if self.embedding_source_column and self.embedding_model_endpoint_name:
                    # Databricks will compute embeddings
                    self.index = self.client.create_delta_sync_index(
                        endpoint_name=self.endpoint_name,
                        source_table_name=self.source_table_name,
                        index_name=self.index_name,
                        pipeline_type=self.pipeline_type,
                        primary_key=self.primary_key,
                        embedding_source_column=self.embedding_source_column,
                        embedding_model_endpoint_name=self.embedding_model_endpoint_name
                    )
                else:
                    # Self-managed embeddings
                    self.index = self.client.create_delta_sync_index(
                        endpoint_name=self.endpoint_name,
                        source_table_name=self.source_table_name,
                        index_name=self.index_name,
                        pipeline_type=self.pipeline_type,
                        primary_key=self.primary_key,
                        embedding_dimension=self.embedding_dimension,
                        embedding_vector_column=self.embedding_vector_column
                    )
                
                logger.info(f"Successfully created vector search index '{self.index_name}'")
            except Exception as e:
                logger.error(f"Failed to create vector search index '{self.index_name}': {e}")
                raise

    def create_col(self, name=None, vector_size=None, distance=None):
        """
        Create a new collection (index).
        
        Args:
            name (str, optional): Index name. If provided, will create a new index.
            vector_size (int, optional): Vector dimension size.
            distance (str, optional): Distance metric (not directly applicable for Databricks).
        
        Returns:
            The index object.
        """
        if name:
            # Create a new index with the specified name
            new_index_name = f"{name}"
            new_source_table = f"{name}_table"
            
            try:
                logger.info(f"Creating new vector search index '{new_index_name}'")
                
                if self.embedding_source_column and self.embedding_model_endpoint_name:
                    # Databricks will compute embeddings
                    new_index = self.client.create_delta_sync_index(
                        endpoint_name=self.endpoint_name,
                        source_table_name=new_source_table,
                        index_name=new_index_name,
                        pipeline_type=self.pipeline_type,
                        primary_key=self.primary_key,
                        embedding_source_column=self.embedding_source_column,
                        embedding_model_endpoint_name=self.embedding_model_endpoint_name
                    )
                else:
                    # Self-managed embeddings
                    embedding_dims = vector_size or self.embedding_dimension
                    new_index = self.client.create_delta_sync_index(
                        endpoint_name=self.endpoint_name,
                        source_table_name=new_source_table,
                        index_name=new_index_name,
                        pipeline_type=self.pipeline_type,
                        primary_key=self.primary_key,
                        embedding_dimension=embedding_dims,
                        embedding_vector_column=self.embedding_vector_column
                    )
                
                # Update current index if creating a new collection
                self.index = new_index
                self.index_name = new_index_name
                self.source_table_name = new_source_table
                
                return new_index
            except Exception as e:
                logger.error(f"Failed to create new index '{new_index_name}': {e}")
                raise
        
        return self.index

    def insert(self, vectors: list, payloads: list = None, ids: list = None):
        """
        Insert vectors into the Delta table (will sync to index).
        
        Note: For Delta Sync Index, vectors are typically inserted into the source Delta table,
        not directly into the index. This is a simplified implementation for compatibility.
        """
        logger.warning("Direct vector insertion not supported with Delta Sync Index. "
                      "Vectors should be inserted into the source Delta table.")
        # In a real implementation, you would insert into the Delta table
        # and trigger sync, but for the interface compatibility, we'll handle this gracefully
        pass

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
            filter_dict = {}
            if filters:
                # Convert filters based on endpoint type
                if self.endpoint_type == "STORAGE_OPTIMIZED":
                    # Storage-optimized uses SQL-like filter strings
                    filter_conditions = []
                    for key, value in filters.items():
                        if value is not None:
                            if isinstance(value, str):
                                filter_conditions.append(f"{key} = '{value}'")
                            else:
                                filter_conditions.append(f"{key} = {value}")
                    if filter_conditions:
                        filter_dict["filters"] = " AND ".join(filter_conditions)
                else:
                    # Standard endpoint uses dictionary filters
                    filter_dict["filters"] = {k: v for k, v in filters.items() if v is not None}

            # Perform vector search
            if self.embedding_source_column and query:
                # Text-based search (Databricks computes embeddings)
                results = self.index.similarity_search(
                    query_text=query,
                    num_results=limit,
                    **filter_dict
                )
            else:
                # Vector-based search (self-managed embeddings) 
                results = self.index.similarity_search(
                    query_vector=vectors,
                    num_results=limit,
                    **filter_dict
                )

            # Convert results to MemoryResult format
            memory_results = []
            for result in results.get("result", {}).get("data_array", []):
                # Extract metadata and score
                score = result.get("score")
                row_data = result
                
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
                memory_results.append(MemoryResult(id=memory_id, score=score, payload=payload))
            
            return memory_results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def delete(self, vector_id):
        """
        Delete a vector by ID.
        
        Note: For Delta Sync Index, deletion should happen in the source Delta table.
        """
        logger.warning(f"Direct vector deletion not supported with Delta Sync Index. "
                      f"Vector with ID {vector_id} should be deleted from the source Delta table.")
        # In a real implementation, you would delete from the Delta table
        pass

    def update(self, vector_id=None, vector=None, payload=None):
        """
        Update a vector and its payload.
        
        Note: For Delta Sync Index, updates should happen in the source Delta table.
        """
        logger.warning(f"Direct vector update not supported with Delta Sync Index. "
                      f"Vector with ID {vector_id} should be updated in the source Delta table.")
        # In a real implementation, you would update the Delta table
        pass

    def get(self, vector_id):
        """
        Retrieve a vector by ID.
        
        Args:
            vector_id (str): ID of the vector to retrieve.
        
        Returns:
            MemoryResult: The retrieved vector.
        """
        try:
            # Use similarity search with ID filter to retrieve the specific vector
            filters = {self.primary_key: vector_id}
            
            if self.endpoint_type == "STORAGE_OPTIMIZED":
                filter_str = f"{self.primary_key} = '{vector_id}'"
                results = self.index.similarity_search(
                    query_text="",  # Empty query, rely on filters
                    num_results=1,
                    filters=filter_str
                )
            else:
                results = self.index.similarity_search(
                    query_text="",  # Empty query, rely on filters
                    num_results=1,
                    filters=filters
                )
            
            data_array = results.get("result", {}).get("data_array", [])
            if not data_array:
                raise KeyError(f"Vector with ID {vector_id} not found")
            
            row_data = data_array[0]
            
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

    def list_cols(self):
        """
        List all collections (indexes).
        
        Returns:
            List of index names.
        """
        try:
            indexes = self.client.list_indexes(endpoint_name=self.endpoint_name)
            return [idx.name for idx in indexes.get("vector_indexes", [])]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            raise

    def delete_col(self):
        """
        Delete the current collection (index).
        """
        try:
            self.client.delete_index(self.index_name)
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
            index = self.client.get_index(index_name)
            return index.describe()
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
            filter_dict = {}
            if filters:
                if self.endpoint_type == "STORAGE_OPTIMIZED":
                    # Storage-optimized uses SQL-like filter strings
                    filter_conditions = []
                    for key, value in filters.items():
                        if value is not None:
                            if isinstance(value, str):
                                filter_conditions.append(f"{key} = '{value}'")
                            else:
                                filter_conditions.append(f"{key} = {value}")
                    if filter_conditions:
                        filter_dict["filters"] = " AND ".join(filter_conditions)
                else:
                    # Standard endpoint uses dictionary filters
                    filter_dict["filters"] = {k: v for k, v in filters.items() if v is not None}

            # Get results
            num_results = limit or 100  # Default limit
            results = self.index.similarity_search(
                query_text="",  # Empty query to get all
                num_results=num_results,
                **filter_dict
            )

            # Convert results to MemoryResult format
            memory_results = []
            for result in results.get("result", {}).get("data_array", []):
                row_data = result
                
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
            self._ensure_index_exists()
            
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
