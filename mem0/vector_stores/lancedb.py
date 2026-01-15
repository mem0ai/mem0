import json
import logging
import uuid
from typing import Any, Dict, List, Optional

import numpy as np
from pydantic import BaseModel

try:
    import lancedb
except ImportError:
    raise ImportError(
        "LanceDB vector store requires lancedb. "
        "Please install it using 'pip install lancedb'"
    )

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class LanceDB(VectorStoreBase):
    def __init__(
        self,
        uri: str = "./lancedb",
        collection_name: str = "memories",
        embedding_model_dims: int = 1536,
        table_name: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the LanceDB vector store.

        Args:
            uri (str): URI for LanceDB database (file path or connection string)
            collection_name (str): Collection/table name (default: "memories")
            embedding_model_dims (int): Dimension of the embedding vector (default: 1536)
            table_name (str, optional): Override table name (uses collection_name if not provided)
            **kwargs: Additional arguments passed to LanceDB
        """
        self.uri = uri
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.table_name = table_name or collection_name
        self.kwargs = kwargs

        # Initialize LanceDB connection
        self.db = None
        self.table = None
        self._setup_connection()
        
        # Create table if it doesn't exist
        self._create_table()

    def _setup_connection(self):
        """Setup LanceDB connection."""
        try:
            self.db = lancedb.connect(self.uri)
            logger.info(f"Successfully connected to LanceDB at {self.uri}")
        except Exception as e:
            logger.error(f"Failed to connect to LanceDB: {e}")
            raise

    def _create_table(self):
        """Create table if it doesn't exist."""
        try:
            # Check if table exists
            if self.table_name in self.db.table_names():
                self.table = self.db.open_table(self.table_name)
                logger.info(f"Opened existing table '{self.table_name}'")
            else:
                # Create empty table with schema
                schema = {
                    "id": "string",
                    "vector": f"float[{self.embedding_model_dims}]",
                    "payload": "string"
                }
                
                # Create empty table with proper schema
                empty_data = []
                self.table = self.db.create_table(self.table_name, empty_data, schema=schema)
                logger.info(f"Created table '{self.table_name}' with vector dimension {self.embedding_model_dims}")
        except Exception as e:
            logger.error(f"Failed to create/open table: {e}")
            raise

    def create_col(self, name: str = None, vector_size: int = None, distance: str = "cosine"):
        """
        Create a new collection (table in LanceDB).

        Args:
            name (str, optional): Collection name (uses self.collection_name if not provided)
            vector_size (int, optional): Vector dimension (uses self.embedding_model_dims if not provided)
            distance (str): Distance metric (cosine, euclidean, dot_product)
        """
        table_name = name or self.collection_name
        dims = vector_size or self.embedding_model_dims

        try:
            if table_name in self.db.table_names():
                logger.info(f"Table '{table_name}' already exists")
                return

            # Create empty table with schema
            schema = {
                "id": "string",
                "vector": f"float[{dims}]",
                "payload": "string"
            }
            
            empty_data = []
            self.db.create_table(table_name, empty_data, schema=schema)
            logger.info(f"Created collection '{table_name}' with vector dimension {dims}")
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise

    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None
    ):
        """
        Insert vectors into the collection.

        Args:
            vectors (List[List[float]]): List of vectors to insert
            payloads (List[Dict], optional): List of payloads corresponding to vectors
            ids (List[str], optional): List of IDs corresponding to vectors
        """
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")

        if payloads is None:
            payloads = [{}] * len(vectors)
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]

        try:
            # Prepare data for insertion
            data = []
            for vector, payload, vec_id in zip(vectors, payloads, ids):
                data.append({
                    "id": vec_id,
                    "vector": vector,
                    "payload": json.dumps(payload)
                })

            # Insert data into table
            self.table.add(data)
            logger.info(f"Successfully inserted {len(data)} vectors")
        except Exception as e:
            logger.error(f"Failed to insert vectors: {e}")
            raise

    def search(
        self,
        query: str,
        vectors: List[float],
        limit: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[OutputData]:
        """
        Search for similar vectors using cosine similarity.

        Args:
            query (str): Query string (not used in vector search)
            vectors (List[float]): Query vector
            limit (int): Number of results to return
            filters (Dict, optional): Filters to apply to the search

        Returns:
            List[OutputData]: Search results
        """
        try:
            # Convert query vector to numpy array
            query_vector = np.array(vectors)
            
            # Perform vector search using LanceDB's search functionality
            if filters:
                # Build filter expression for LanceDB
                filter_expr = self._build_filter_expression(filters)
                results = self.table.search(query_vector).where(filter_expr).limit(limit).to_pandas()
            else:
                results = self.table.search(query_vector).limit(limit).to_pandas()

            # Convert results to OutputData format
            output_results = []
            for _, row in results.iterrows():
                try:
                    payload = json.loads(row['payload']) if row['payload'] else {}
                except json.JSONDecodeError:
                    payload = {}
                
                # Calculate distance (LanceDB returns similarity, we need distance)
                distance = 1 - row.get('_distance', 0.0) if '_distance' in row else 0.0
                
                output_results.append(OutputData(
                    id=row['id'],
                    score=float(distance),
                    payload=payload
                ))

            return output_results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def _build_filter_expression(self, filters: Dict) -> str:
        """Build LanceDB filter expression from filters dict."""
        conditions = []
        for key, value in filters.items():
            if isinstance(value, str):
                conditions.append(f"JSON_EXTRACT(payload, '$.{key}') = '{value}'")
            else:
                conditions.append(f"JSON_EXTRACT(payload, '$.{key}') = {value}")
        return " AND ".join(conditions)

    def delete(self, vector_id: str):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete
        """
        try:
            # LanceDB doesn't have direct delete by ID, so we need to filter and delete
            self.table.delete(f"id = '{vector_id}'")
            logger.info(f"Deleted vector with id: {vector_id}")
        except Exception as e:
            logger.error(f"Failed to delete vector: {e}")
            raise

    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None,
    ):
        """
        Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update
            vector (List[float], optional): Updated vector
            payload (Dict, optional): Updated payload
        """
        try:
            # Get existing record
            existing = self.table.search().where(f"id = '{vector_id}'").to_pandas()
            if existing.empty:
                logger.warning(f"Vector with id {vector_id} not found for update")
                return

            # Prepare update data
            update_data = {"id": vector_id}
            if vector is not None:
                update_data["vector"] = vector
            if payload is not None:
                update_data["payload"] = json.dumps(payload)

            # Delete old record and insert updated one
            self.table.delete(f"id = '{vector_id}'")
            self.table.add([update_data])
            
            logger.info(f"Updated vector with id: {vector_id}")
        except Exception as e:
            logger.error(f"Failed to update vector: {e}")
            raise

    def get(self, vector_id: str) -> Optional[OutputData]:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve

        Returns:
            OutputData: Retrieved vector or None if not found
        """
        try:
            results = self.table.search().where(f"id = '{vector_id}'").to_pandas()
            
            if results.empty:
                return None

            row = results.iloc[0]
            try:
                payload = json.loads(row['payload']) if row['payload'] else {}
            except json.JSONDecodeError:
                payload = {}

            return OutputData(
                id=row['id'],
                score=None,
                payload=payload
            )
        except Exception as e:
            logger.error(f"Failed to get vector: {e}")
            return None

    def list_cols(self) -> List[str]:
        """
        List all collections (tables).

        Returns:
            List[str]: List of collection names
        """
        try:
            return self.db.table_names()
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    def delete_col(self):
        """Delete the collection (table)."""
        try:
            self.db.drop_table(self.table_name)
            logger.info(f"Deleted collection '{self.table_name}'")
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            raise

    def col_info(self) -> Dict[str, Any]:
        """
        Get information about the collection.

        Returns:
            Dict[str, Any]: Collection information
        """
        try:
            # Get table info
            count = len(self.table.to_pandas())
            
            return {
                "name": self.table_name,
                "count": count,
                "vector_dims": self.embedding_model_dims,
                "uri": self.uri
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {}

    def list(
        self,
        filters: Optional[Dict] = None,
        limit: int = 100
    ) -> List[List[OutputData]]:
        """
        List all vectors in the collection.

        Args:
            filters (Dict, optional): Filters to apply
            limit (int): Number of vectors to return

        Returns:
            List[List[OutputData]]: List of vectors
        """
        try:
            # Get all data from table
            query = self.table.search()
            
            if filters:
                filter_expr = self._build_filter_expression(filters)
                query = query.where(filter_expr)
            
            results = query.limit(limit).to_pandas()

            output_results = []
            for _, row in results.iterrows():
                try:
                    payload = json.loads(row['payload']) if row['payload'] else {}
                except json.JSONDecodeError:
                    payload = {}

                output_results.append(OutputData(
                    id=row['id'],
                    score=None,
                    payload=payload
                ))

            return [output_results]
        except Exception as e:
            logger.error(f"Failed to list vectors: {e}")
            return [[]]

    def reset(self):
        """Reset the collection by deleting and recreating it."""
        try:
            logger.warning(f"Resetting collection {self.table_name}...")
            self.delete_col()
            self._create_table()
            logger.info(f"Collection '{self.table_name}' has been reset")
        except Exception as e:
            logger.error(f"Failed to reset collection: {e}")
            raise

    def __del__(self):
        """Cleanup when the object is deleted."""
        try:
            if self.db:
                # LanceDB doesn't require explicit connection cleanup
                pass
        except Exception:
            pass
