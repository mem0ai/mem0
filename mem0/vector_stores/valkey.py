import json
import logging
from datetime import datetime

import numpy as np
import pytz
import valkey
from valkey.exceptions import ResponseError

from mem0.memory.utils import extract_json
from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

# Default fields for the Valkey index
DEFAULT_FIELDS = [
    {"name": "memory_id", "type": "tag"},
    {"name": "hash", "type": "tag"},
    {"name": "agent_id", "type": "tag"},
    {"name": "run_id", "type": "tag"},
    {"name": "user_id", "type": "tag"},
    {"name": "memory", "type": "tag"},  # Using TAG instead of TEXT for Valkey compatibility
    {"name": "metadata", "type": "tag"},  # Using TAG instead of TEXT for Valkey compatibility
    {"name": "created_at", "type": "numeric"},
    {"name": "updated_at", "type": "numeric"},
    {
        "name": "embedding",
        "type": "vector",
        "attrs": {"distance_metric": "cosine", "algorithm": "flat", "datatype": "float32"},
    },
]

excluded_keys = {"user_id", "agent_id", "run_id", "hash", "data", "created_at", "updated_at"}


class MemoryResult:
    def __init__(self, id: str, payload: dict, score: float = None):
        self.id = id
        self.payload = payload
        self.score = score


class ValkeyDB(VectorStoreBase):
    def __init__(
        self,
        valkey_url: str,
        collection_name: str,
        embedding_model_dims: int,
        timezone: str = "UTC",
        index_type: str = "hnsw",
        hnsw_m: int = 16,
        hnsw_ef_construction: int = 200,
        hnsw_ef_runtime: int = 10,
    ):
        """
        Initialize the Valkey vector store.

        Args:
            valkey_url (str): Valkey URL.
            collection_name (str): Collection name.
            embedding_model_dims (int): Embedding model dimensions.
            timezone (str, optional): Timezone for timestamps. Defaults to "UTC".
            index_type (str, optional): Index type ('hnsw' or 'flat'). Defaults to "hnsw".
            hnsw_m (int, optional): HNSW M parameter (connections per node). Defaults to 16.
            hnsw_ef_construction (int, optional): HNSW ef_construction parameter. Defaults to 200.
            hnsw_ef_runtime (int, optional): HNSW ef_runtime parameter. Defaults to 10.
        """
        self.embedding_model_dims = embedding_model_dims
        self.collection_name = collection_name
        self.prefix = f"mem0:{collection_name}"
        self.timezone = timezone
        self.index_type = index_type.lower()
        self.hnsw_m = hnsw_m
        self.hnsw_ef_construction = hnsw_ef_construction
        self.hnsw_ef_runtime = hnsw_ef_runtime

        # Validate index type
        if self.index_type not in ["hnsw", "flat"]:
            raise ValueError(f"Invalid index_type: {index_type}. Must be 'hnsw' or 'flat'")

        # Connect to Valkey
        try:
            self.client = valkey.from_url(valkey_url)
            logger.debug(f"Successfully connected to Valkey at {valkey_url}")
        except Exception as e:
            logger.exception(f"Failed to connect to Valkey at {valkey_url}: {e}")
            raise

        # Create the index schema
        self._create_index(embedding_model_dims)

    def _create_index(self, embedding_model_dims):
        """
        Create the search index with the specified schema.

        Args:
            embedding_model_dims (int): Dimensions for the vector embeddings.

        Raises:
            ValueError: If the search module is not available.
            Exception: For other errors during index creation.
        """
        # Check if the search module is available
        try:
            # Try to execute a search command
            self.client.execute_command("FT._LIST")
        except ResponseError as e:
            if "unknown command" in str(e).lower():
                raise ValueError(
                    "Valkey search module is not available. Please ensure Valkey is running with the search module enabled. "
                    "The search module can be loaded using the --loadmodule option with the valkey-search library. "
                    "For installation and setup instructions, refer to the Valkey Search documentation."
                )
            else:
                logger.exception(f"Error checking search module: {e}")
                raise

        # Check if the index already exists
        try:
            self.client.ft(self.collection_name).info()
            return
        except ResponseError as e:
            if "not found" not in str(e).lower():
                logger.exception(f"Error checking index existence: {e}")
                raise

        # Build the vector field configuration based on index type
        if self.index_type == "hnsw":
            vector_config = [
                "embedding",
                "VECTOR",
                "HNSW",
                "12",  # Attribute count: TYPE, FLOAT32, DIM, dims, DISTANCE_METRIC, COSINE, M, m, EF_CONSTRUCTION, ef_construction, EF_RUNTIME, ef_runtime
                "TYPE",
                "FLOAT32",
                "DIM",
                str(embedding_model_dims),
                "DISTANCE_METRIC",
                "COSINE",
                "M",
                str(self.hnsw_m),
                "EF_CONSTRUCTION",
                str(self.hnsw_ef_construction),
                "EF_RUNTIME",
                str(self.hnsw_ef_runtime),
            ]
        else:  # flat
            vector_config = [
                "embedding",
                "VECTOR",
                "FLAT",
                "6",  # Attribute count: TYPE, FLOAT32, DIM, dims, DISTANCE_METRIC, COSINE
                "TYPE",
                "FLOAT32",
                "DIM",
                str(embedding_model_dims),
                "DISTANCE_METRIC",
                "COSINE",
            ]

        # Create the index using raw command
        cmd = [
            "FT.CREATE",
            self.collection_name,
            "ON",
            "HASH",
            "PREFIX",
            "1",
            self.prefix,
            "SCHEMA",
            "memory_id",
            "TAG",
            "SEPARATOR",
            ",",
            "hash",
            "TAG",
            "SEPARATOR",
            ",",
            "agent_id",
            "TAG",
            "SEPARATOR",
            ",",
            "run_id",
            "TAG",
            "SEPARATOR",
            ",",
            "user_id",
            "TAG",
            "SEPARATOR",
            ",",
            "memory",
            "TAG",
            "SEPARATOR",
            ",",
            "metadata",
            "TAG",
            "SEPARATOR",
            ",",
            "created_at",
            "NUMERIC",
            "updated_at",
            "NUMERIC",
        ] + vector_config

        try:
            self.client.execute_command(*cmd)
        except Exception as e:
            logger.exception(f"Error creating index {self.collection_name}: {e}")
            raise

    def create_col(self, name=None, vector_size=None, distance=None):
        """
        Create a new collection (index) in Valkey.

        Args:
            name (str, optional): Name for the collection. Defaults to None, which uses the current collection_name.
            vector_size (int, optional): Size of the vector embeddings. Defaults to None, which uses the current embedding_model_dims.
            distance (str, optional): Distance metric to use. Defaults to None, which uses 'cosine'.

        Returns:
            The created index object.
        """
        # Use provided parameters or fall back to instance attributes
        collection_name = name or self.collection_name
        embedding_dims = vector_size or self.embedding_model_dims
        distance_metric = distance or "COSINE"
        prefix = f"mem0:{collection_name}"

        # Try to drop the index if it exists
        try:
            self._drop_index(collection_name)
        except Exception as e:
            logger.warning(f"Error dropping existing index {collection_name}: {e}")

        # Build the vector field configuration based on index type
        if self.index_type == "hnsw":
            vector_config = [
                "embedding",
                "VECTOR",
                "HNSW",
                "12",  # Attribute count: TYPE, FLOAT32, DIM, dims, DISTANCE_METRIC, metric, M, m, EF_CONSTRUCTION, ef_construction, EF_RUNTIME, ef_runtime
                "TYPE",
                "FLOAT32",
                "DIM",
                str(embedding_dims),
                "DISTANCE_METRIC",
                distance_metric,
                "M",
                str(self.hnsw_m),
                "EF_CONSTRUCTION",
                str(self.hnsw_ef_construction),
                "EF_RUNTIME",
                str(self.hnsw_ef_runtime),
            ]
        else:  # flat
            vector_config = [
                "embedding",
                "VECTOR",
                "FLAT",
                "6",  # Attribute count: TYPE, FLOAT32, DIM, dims, DISTANCE_METRIC, metric
                "TYPE",
                "FLOAT32",
                "DIM",
                str(embedding_dims),
                "DISTANCE_METRIC",
                distance_metric,
            ]

        # Create the index using raw command
        cmd = [
            "FT.CREATE",
            collection_name,
            "ON",
            "HASH",
            "PREFIX",
            "1",
            prefix,
            "SCHEMA",
            "memory_id",
            "TAG",
            "SEPARATOR",
            ",",
            "hash",
            "TAG",
            "SEPARATOR",
            ",",
            "agent_id",
            "TAG",
            "SEPARATOR",
            ",",
            "run_id",
            "TAG",
            "SEPARATOR",
            ",",
            "user_id",
            "TAG",
            "SEPARATOR",
            ",",
            "memory",
            "TAG",
            "SEPARATOR",
            ",",
            "metadata",
            "TAG",
            "SEPARATOR",
            ",",
            "created_at",
            "NUMERIC",
            "updated_at",
            "NUMERIC",
        ] + vector_config

        try:
            self.client.execute_command(*cmd)
            logger.info(f"Successfully created {self.index_type.upper()} index {collection_name}")

            # Update instance attributes if creating a new collection
            if name:
                self.collection_name = collection_name
                self.prefix = prefix

            return self.client.ft(collection_name)
        except Exception as e:
            logger.exception(f"Error creating collection {collection_name}: {e}")
            raise

    def insert(self, vectors: list, payloads: list = None, ids: list = None):
        """
        Insert vectors and their payloads into the index.

        Args:
            vectors (list): List of vectors to insert.
            payloads (list, optional): List of payloads corresponding to the vectors.
            ids (list, optional): List of IDs for the vectors.
        """
        for vector, payload, id in zip(vectors, payloads, ids):
            try:
                # Create the key for the hash
                key = f"{self.prefix}:{id}"

                # Check for required fields and provide defaults if missing
                if "data" not in payload:
                    # Silently use default value for missing 'data' field
                    pass

                # Ensure created_at is present
                if "created_at" not in payload:
                    payload["created_at"] = datetime.now(pytz.timezone(self.timezone)).isoformat()

                # Prepare the hash data
                hash_data = {
                    "memory_id": id,
                    "hash": payload.get("hash", f"hash_{id}"),  # Use a default hash if not provided
                    "memory": payload.get("data", f"data_{id}"),  # Use a default data if not provided
                    "created_at": int(datetime.fromisoformat(payload["created_at"]).timestamp()),
                    "embedding": np.array(vector, dtype=np.float32).tobytes(),
                }

                # Add optional fields
                for field in ["agent_id", "run_id", "user_id"]:
                    if field in payload:
                        hash_data[field] = payload[field]

                # Add metadata
                hash_data["metadata"] = json.dumps({k: v for k, v in payload.items() if k not in excluded_keys})

                # Store in Valkey
                self.client.hset(key, mapping=hash_data)
                logger.debug(f"Successfully inserted vector with ID {id}")
            except KeyError as e:
                logger.error(f"Error inserting vector with ID {id}: Missing required field {e}")
            except Exception as e:
                logger.exception(f"Error inserting vector with ID {id}: {e}")
                raise

    def _build_search_query(self, knn_part, filters=None):
        """
        Build a search query string with filters.

        Args:
            knn_part (str): The KNN part of the query.
            filters (dict, optional): Filters to apply to the search.

        Returns:
            str: The complete search query string.
        """
        # No filters, just use the KNN search
        if not filters or not any(value is not None for key, value in filters.items()):
            return f"*=>{knn_part}"

        # Build filter expression
        filter_parts = []
        for key, value in filters.items():
            if value is not None:
                # Use the correct filter syntax for Valkey
                filter_parts.append(f"@{key}:{{{value}}}")

        # No valid filter parts
        if not filter_parts:
            return f"*=>{knn_part}"

        # Combine filter parts with proper syntax
        filter_expr = " ".join(filter_parts)
        return f"{filter_expr} =>{knn_part}"

    def _execute_search_with_fallback(self, query, params):
        """
        Execute a search query with fallback options if the initial query fails.

        Args:
            query (str): The search query to execute.
            params (dict): The query parameters.

        Returns:
            The search results.
        """
        try:
            # Execute the search
            return self.client.ft(self.collection_name).search(query, query_params=params)
        except ResponseError as e:
            logger.warning(f"Search error: {e}")

            # Try alternative syntax if the first attempt fails
            if "Invalid filter expression" in str(e):
                logger.warning("Trying alternative filter syntax")

                # Try with parentheses around the filter expression
                if not query.startswith("*"):
                    alternative_query = f"({query.split(' =>')[0]}) =>{query.split(' =>')[1]}"
                    logger.info(f"Retry with query: {alternative_query}")

                    try:
                        return self.client.ft(self.collection_name).search(alternative_query, query_params=params)
                    except ResponseError as e2:
                        logger.warning(f"Second attempt failed: {e2}")

                # Last resort: try without filters
                logger.warning("Falling back to search without filters")
                fallback_query = f"*=>{query.split(' =>')[1]}" if "=>" in query else query
                return self.client.ft(self.collection_name).search(fallback_query, query_params=params)
            else:
                # Re-raise other exceptions
                raise

    def _process_search_results(self, results):
        """
        Process search results into MemoryResult objects.

        Args:
            results: The search results from Valkey.

        Returns:
            list: List of MemoryResult objects.
        """
        memory_results = []
        for doc in results.docs:
            # Extract the score
            score = float(doc.vector_score) if hasattr(doc, "vector_score") else None

            # Create the payload
            payload = {
                "hash": doc.hash,
                "data": doc.memory,
                "created_at": self._format_timestamp(int(doc.created_at), self.timezone),
            }

            # Add updated_at if available
            if hasattr(doc, "updated_at"):
                payload["updated_at"] = self._format_timestamp(int(doc.updated_at), self.timezone)

            # Add optional fields
            for field in ["agent_id", "run_id", "user_id"]:
                if hasattr(doc, field):
                    payload[field] = getattr(doc, field)

            # Add metadata
            if hasattr(doc, "metadata"):
                try:
                    metadata = json.loads(extract_json(doc.metadata))
                    payload.update(metadata)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Failed to parse metadata: {e}")

            # Create the result
            memory_results.append(MemoryResult(id=doc.memory_id, score=score, payload=payload))

        return memory_results

    def search(self, query: str, vectors: list, limit: int = 5, filters: dict = None, ef_runtime: int = None):
        """
        Search for similar vectors in the index.

        Args:
            query (str): The search query.
            vectors (list): The vector to search for.
            limit (int, optional): Maximum number of results to return. Defaults to 5.
            filters (dict, optional): Filters to apply to the search. Defaults to None.
            ef_runtime (int, optional): HNSW ef_runtime parameter for this query. Only used with HNSW index. Defaults to None.

        Returns:
            list: List of MemoryResult objects.
        """
        # Convert the vector to bytes
        vector_bytes = np.array(vectors, dtype=np.float32).tobytes()

        # Build the KNN part with optional EF_RUNTIME for HNSW
        if self.index_type == "hnsw" and ef_runtime is not None:
            knn_part = f"[KNN {limit} @embedding $vec_param EF_RUNTIME {ef_runtime} AS vector_score]"
        else:
            knn_part = f"[KNN {limit} @embedding $vec_param AS vector_score]"

        # Build the complete query
        q = self._build_search_query(knn_part, filters)

        # Log the query for debugging (only in debug mode)
        logger.debug(f"Valkey search query: {q}")

        # Set up the query parameters
        params = {"vec_param": vector_bytes}

        # Execute the search with fallback
        results = self._execute_search_with_fallback(q, params)

        # Process the results
        return self._process_search_results(results)

    def delete(self, vector_id):
        """
        Delete a vector from the index.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        try:
            key = f"{self.prefix}:{vector_id}"
            self.client.delete(key)
            logger.debug(f"Successfully deleted vector with ID {vector_id}")
        except Exception as e:
            logger.exception(f"Error deleting vector with ID {vector_id}: {e}")
            raise

    def update(self, vector_id=None, vector=None, payload=None):
        """
        Update a vector in the index.

        Args:
            vector_id (str): ID of the vector to update.
            vector (list, optional): New vector data.
            payload (dict, optional): New payload data.
        """
        try:
            key = f"{self.prefix}:{vector_id}"

            # Check for required fields and provide defaults if missing
            if "data" not in payload:
                # Silently use default value for missing 'data' field
                pass

            # Ensure created_at is present
            if "created_at" not in payload:
                payload["created_at"] = datetime.now(pytz.timezone(self.timezone)).isoformat()

            # Prepare the hash data
            hash_data = {
                "memory_id": vector_id,
                "hash": payload.get("hash", f"hash_{vector_id}"),  # Use a default hash if not provided
                "memory": payload.get("data", f"data_{vector_id}"),  # Use a default data if not provided
                "created_at": int(datetime.fromisoformat(payload["created_at"]).timestamp()),
                "embedding": np.array(vector, dtype=np.float32).tobytes(),
            }

            # Add updated_at if available
            if "updated_at" in payload:
                hash_data["updated_at"] = int(datetime.fromisoformat(payload["updated_at"]).timestamp())

            # Add optional fields
            for field in ["agent_id", "run_id", "user_id"]:
                if field in payload:
                    hash_data[field] = payload[field]

            # Add metadata
            hash_data["metadata"] = json.dumps({k: v for k, v in payload.items() if k not in excluded_keys})

            # Update in Valkey
            self.client.hset(key, mapping=hash_data)
            logger.debug(f"Successfully updated vector with ID {vector_id}")
        except KeyError as e:
            logger.error(f"Error updating vector with ID {vector_id}: Missing required field {e}")
        except Exception as e:
            logger.exception(f"Error updating vector with ID {vector_id}: {e}")
            raise

    def _format_timestamp(self, timestamp, timezone=None):
        """
        Format a timestamp with the specified timezone.

        Args:
            timestamp (int): The timestamp to format.
            timezone (str, optional): The timezone to use. Defaults to UTC.

        Returns:
            str: The formatted timestamp.
        """
        # Use UTC as default timezone if not specified
        tz = pytz.timezone(timezone or "UTC")
        return datetime.fromtimestamp(timestamp, tz=tz).isoformat(timespec="microseconds")

    def _process_document_fields(self, result, vector_id):
        """
        Process document fields from a Valkey hash result.

        Args:
            result (dict): The hash result from Valkey.
            vector_id (str): The vector ID.

        Returns:
            dict: The processed payload.
            str: The memory ID.
        """
        # Create the payload with error handling
        payload = {}

        # Convert bytes to string for text fields
        for k in result:
            if k not in ["embedding"]:
                if isinstance(result[k], bytes):
                    try:
                        result[k] = result[k].decode("utf-8")
                    except UnicodeDecodeError:
                        # If decoding fails, keep the bytes
                        pass

        # Add required fields with error handling
        for field in ["hash", "memory", "created_at"]:
            if field in result:
                if field == "created_at":
                    try:
                        payload[field] = self._format_timestamp(int(result[field]), self.timezone)
                    except (ValueError, TypeError):
                        payload[field] = result[field]
                else:
                    payload[field] = result[field]
            else:
                # Use default values for missing fields
                if field == "hash":
                    payload[field] = "unknown"
                elif field == "memory":
                    payload[field] = "unknown"
                elif field == "created_at":
                    payload[field] = self._format_timestamp(
                        int(datetime.now(tz=pytz.timezone(self.timezone)).timestamp()), self.timezone
                    )

        # Rename memory to data for consistency
        if "memory" in payload:
            payload["data"] = payload.pop("memory")

        # Add updated_at if available
        if "updated_at" in result:
            try:
                payload["updated_at"] = self._format_timestamp(int(result["updated_at"]), self.timezone)
            except (ValueError, TypeError):
                payload["updated_at"] = result["updated_at"]

        # Add optional fields
        for field in ["agent_id", "run_id", "user_id"]:
            if field in result:
                payload[field] = result[field]

        # Add metadata
        if "metadata" in result:
            try:
                metadata = json.loads(extract_json(result["metadata"]))
                payload.update(metadata)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Failed to parse metadata: {result.get('metadata')}")

        # Use memory_id from result if available, otherwise use vector_id
        memory_id = result.get("memory_id", vector_id)

        return payload, memory_id

    def get(self, vector_id):
        """
        Get a vector by ID.

        Args:
            vector_id (str): ID of the vector to get.

        Returns:
            MemoryResult: The retrieved vector.
        """
        try:
            key = f"{self.prefix}:{vector_id}"
            result = self.client.hgetall(key)

            if not result:
                raise KeyError(f"Vector with ID {vector_id} not found")

            logger.debug(f"Retrieved result keys: {result.keys()}")

            # Process the document fields
            payload, memory_id = self._process_document_fields(result, vector_id)

            return MemoryResult(id=memory_id, payload=payload)
        except KeyError:
            raise
        except Exception as e:
            logger.exception(f"Error getting vector with ID {vector_id}: {e}")
            raise

    def list_cols(self):
        """
        List all collections (indices) in Valkey.

        Returns:
            list: List of collection names.
        """
        try:
            # Use the FT._LIST command to list all indices
            return self.client.execute_command("FT._LIST")
        except Exception as e:
            logger.exception(f"Error listing collections: {e}")
            raise

    def _drop_index(self, collection_name):
        """
        Drop an index by name using the documented FT.DROPINDEX command.

        Args:
            collection_name (str): Name of the index to drop.
        """
        try:
            self.client.execute_command("FT.DROPINDEX", collection_name)
            logger.info(f"Successfully deleted index {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting index {collection_name}: {e}")
            raise

    def delete_col(self):
        """
        Delete the current collection (index).
        """
        return self._drop_index(self.collection_name)

    def col_info(self, name=None):
        """
        Get information about a collection (index).

        Args:
            name (str, optional): Name of the collection. Defaults to None, which uses the current collection_name.

        Returns:
            dict: Information about the collection.
        """
        try:
            collection_name = name or self.collection_name
            return self.client.ft(collection_name).info()
        except Exception as e:
            logger.exception(f"Error getting collection info for {collection_name}: {e}")
            raise

    def reset(self):
        """
        Reset the index by deleting and recreating it.
        """
        try:
            collection_name = self.collection_name
            logger.warning(f"Resetting index {collection_name}...")

            # Delete the index
            self.delete_col()

            # Recreate the index
            self._create_index(self.embedding_model_dims)

            return True
        except Exception as e:
            logger.exception(f"Error resetting index {self.collection_name}: {e}")
            raise

    def _build_list_query(self, filters=None):
        """
        Build a query for listing vectors.

        Args:
            filters (dict, optional): Filters to apply to the list.

        Returns:
            str: The query string.
        """
        # Default query
        q = "*"

        # Add filters if provided
        if filters and any(value is not None for key, value in filters.items()):
            filter_conditions = []
            for key, value in filters.items():
                if value is not None:
                    filter_conditions.append(f"@{key}:{{{value}}}")

            if filter_conditions:
                q = " ".join(filter_conditions)

        return q

    def list(self, filters: dict = None, limit: int = None) -> list:
        """
        List all recent created memories from the vector store.

        Args:
            filters (dict, optional): Filters to apply to the list. Defaults to None.
            limit (int, optional): Maximum number of results to return. Defaults to None.

        Returns:
            list: List of MemoryResult objects.
        """
        try:
            # Build the query
            q = self._build_list_query(filters)

            # Execute the search with parameters
            if limit is not None:
                results = self.client.ft(self.collection_name).search(q, limit=limit, sortby="created_at", desc=True)
            else:
                results = self.client.ft(self.collection_name).search(q, sortby="created_at", desc=True)

            # Process the results
            memory_results = []
            for doc in results.docs:
                # Process the document fields
                payload = {}

                # Add required fields with error handling
                for field in ["hash", "memory", "created_at"]:
                    if hasattr(doc, field):
                        if field == "created_at":
                            try:
                                payload[field] = self._format_timestamp(int(getattr(doc, field)), self.timezone)
                            except (ValueError, TypeError):
                                payload[field] = getattr(doc, field)
                        else:
                            payload[field] = getattr(doc, field)
                    else:
                        # Use default values for missing fields
                        if field == "hash":
                            payload[field] = "unknown"
                        elif field == "memory":
                            payload[field] = "unknown"
                        elif field == "created_at":
                            payload[field] = self._format_timestamp(
                                int(datetime.now(tz=pytz.timezone(self.timezone)).timestamp()), self.timezone
                            )

                # Rename memory to data for consistency
                if "memory" in payload:
                    payload["data"] = payload.pop("memory")

                # Add updated_at if available
                if hasattr(doc, "updated_at"):
                    try:
                        payload["updated_at"] = self._format_timestamp(int(doc.updated_at), self.timezone)
                    except (ValueError, TypeError):
                        payload["updated_at"] = doc.updated_at

                # Add optional fields
                for field in ["agent_id", "run_id", "user_id"]:
                    if hasattr(doc, field):
                        payload[field] = getattr(doc, field)

                # Add metadata
                if hasattr(doc, "metadata"):
                    try:
                        metadata = json.loads(extract_json(doc.metadata))
                        payload.update(metadata)
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(f"Failed to parse metadata: {getattr(doc, 'metadata', None)}")

                # Use memory_id from doc if available, otherwise use a default
                memory_id = getattr(doc, "memory_id", "unknown")

                # Create the result
                memory_results.append(MemoryResult(id=memory_id, payload=payload))

            return [memory_results]
        except Exception as e:
            logger.exception(f"Error in list method: {e}")
            return [[]]  # Return empty result on error
