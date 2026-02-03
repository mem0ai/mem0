import logging
import time
from importlib.metadata import version
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

try:
    from pymongo import MongoClient
    from pymongo.driver_info import DriverInfo
    from pymongo.errors import PyMongoError
    from pymongo.operations import SearchIndexModel
except ImportError:
    raise ImportError("The 'pymongo' library is required. Please install it using 'pip install pymongo'.")

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

_DRIVER_METADATA = DriverInfo(name="Mem0", version=version("mem0ai"))

class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class MongoDB(VectorStoreBase):
    SIMILARITY_METRIC = "cosine"

    def __init__(
        self,
        db_name: str,
        collection_name: str,
        embedding_model_dims: int,
        mongo_uri: str,
        wait_for_index_ready: bool = True,
        index_creation_timeout: int = 300,
    ):
        """
        Initialize the MongoDB vector store with vector search capabilities.

        Args:
            db_name (str): Database name
            collection_name (str): Collection name
            embedding_model_dims (int): Dimension of the embedding vector
            mongo_uri (str): MongoDB connection URI
            wait_for_index_ready (bool): If True, block until index is queryable after creation.
                                        Set to False for production APIs where index creation
                                        should happen in background. Defaults to True.
            index_creation_timeout (int): Maximum seconds to wait for index creation/deletion.
                                         Increase for large datasets (1M+ vectors). Defaults to 300.
        """
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.db_name = db_name
        self.wait_for_index_ready = wait_for_index_ready
        self.index_creation_timeout = index_creation_timeout

        self.client = MongoClient(mongo_uri, driver=_DRIVER_METADATA)
        self.db = self.client[db_name]
        self.collection = self.create_col()

    def _wait_for_index_status(
        self, collection, index_name: str, target_status: str, timeout: Optional[int] = None
    ) -> bool:
        """
        Polls the index status until it matches the target_status.
        
        MongoDB Atlas Search index operations are asynchronous. This method ensures
        indexes are fully ready before use or completely deleted before recreation.
        
        Args:
            collection: MongoDB collection object
            index_name: Name of the index to check
            target_status: "ready" (wait for queryable=True) or "deleted" (wait for it to disappear)
            timeout: Maximum seconds to wait. Uses self.index_creation_timeout if None.
        
        Returns:
            bool: True if target status reached, False if timeout exceeded
        """
        if timeout is None:
            timeout = self.index_creation_timeout
        
        start_time = time.time()
        poll_interval = 2  # Poll every 2 seconds
        
        while (time.time() - start_time) < timeout:
            indexes = list(collection.list_search_indexes(name=index_name))
            
            if target_status == "deleted":
                if not indexes:
                    logger.info(f"Index '{index_name}' successfully deleted.")
                    return True
            
            elif target_status == "ready":
                if indexes:
                    # Check if the specific index is queryable
                    idx = indexes[0]
                    if idx.get("queryable") is True:
                        logger.info(f"Index '{index_name}' is ready and queryable.")
                        return True
                    # Log status if not ready yet
                    status = idx.get("status", "unknown")
                    logger.debug(f"Index '{index_name}' status: {status}, queryable: {idx.get('queryable', False)}")
            
            time.sleep(poll_interval)
        
        logger.error(
            f"Timeout waiting for index '{index_name}' to become {target_status} "
            f"(waited {timeout}s). Index operations may still be in progress."
        )
        return False

    def create_col(self):
        """
        Create collection and automagically heal legacy knnVector indexes 
        with robust asynchronous operation handling.
        
        MongoDB Atlas Search index operations are asynchronous. This method:
        1. Waits for legacy index deletion to complete before recreating
        2. Optionally waits for new index to become queryable (configurable)
        3. Handles race conditions and timeouts gracefully
        """
        try:
            database = self.client[self.db_name]
            
            # 1. Ensure Collection Exists
            if self.collection_name not in database.list_collection_names():
                logger.info(f"Creating collection '{self.collection_name}'...")
                collection = database[self.collection_name]
                collection.insert_one({"_id": 0, "placeholder": True})
                collection.delete_one({"_id": 0})
                logger.info(f"Collection '{self.collection_name}' created successfully.")
            else:
                collection = database[self.collection_name]

            self.index_name = f"{self.collection_name}_vector_index"
            
            # 2. Inspect Existing Index
            found_indexes = list(collection.list_search_indexes(name=self.index_name))
            should_create_index = True

            if found_indexes:
                existing_index = found_indexes[0]
                definition = existing_index.get("latestDefinition", {})
                
                # Check for legacy criteria
                # Old format: mappings.fields.embedding.type == "knnVector"
                # New format: fields[].type == "vector" and type == "vectorSearch"
                is_legacy = False
                
                # Check if it's using the old mappings structure with knnVector
                mappings = definition.get("mappings", {})
                if mappings:
                    # Old format detected
                    legacy_fields = mappings.get("fields", {})
                    embedding_field = legacy_fields.get("embedding", {})
                    if embedding_field.get("type") == "knnVector":
                        is_legacy = True
                
                # Also check if top-level type is not vectorSearch (covers other legacy formats)
                if definition.get("type") != "vectorSearch":
                    is_legacy = True
                
                # Check new format fields array for knnVector (shouldn't happen, but be safe)
                fields = definition.get("fields", [])
                if not is_legacy and fields:
                    if any(field.get("type") == "knnVector" for field in fields):
                        is_legacy = True

                if is_legacy:
                    logger.warning(f"Legacy 'knnVector' index detected: '{self.index_name}'. Healing...")
                    try:
                        # Drop ONLY the index, preserving data
                        collection.drop_search_index(self.index_name)
                        logger.info(f"Legacy index '{self.index_name}' deletion initiated...")
                        
                        # BLOCKING WAIT: We must ensure it is gone before creating a new one with the same name
                        # Atlas prohibits creating an index if one with the same name is pending deletion
                        if not self._wait_for_index_status(collection, self.index_name, "deleted"):
                            raise PyMongoError(
                                f"Failed to delete legacy index '{self.index_name}' within timeout. "
                                "Index may still be deleting in background."
                            )
                        
                        # should_create_index remains True, so we rebuild it below
                    except PyMongoError as e:
                        logger.error(f"Error dropping legacy index: {e}")
                        return collection
                else:
                    # Index exists and is using the correct modern configuration
                    if self.wait_for_index_ready and not existing_index.get("queryable"):
                        logger.info(
                            f"Index '{self.index_name}' exists but is not ready. Waiting for readiness..."
                        )
                        self._wait_for_index_status(collection, self.index_name, "ready")
                    
                    logger.info(f"Search index '{self.index_name}' is valid and up to date.")
                    should_create_index = False

            # 3. Create Index (if missing or just dropped)
            if should_create_index:
                search_index_model = SearchIndexModel(
                    name=self.index_name,
                    type="vectorSearch",
                    definition={
                        "fields": [
                            {
                                "type": "vector",
                                "path": "embedding",
                                "numDimensions": self.embedding_model_dims,
                                "similarity": self.SIMILARITY_METRIC,
                            }
                        ]
                    },
                )
                try:
                    collection.create_search_index(search_index_model)
                    logger.info(
                        f"Search index '{self.index_name}' creation initiated. "
                        f"(This may take time depending on data size)"
                    )
                    
                    # BLOCKING WAIT: Ensure index is ready before returning (if configured)
                    # Note: Vector index creation can take time depending on data size.
                    # For large datasets (1M+ vectors), increase index_creation_timeout.
                    if self.wait_for_index_ready:
                        if not self._wait_for_index_status(collection, self.index_name, "ready"):
                            logger.warning(
                                f"Index '{self.index_name}' creation initiated but not ready within timeout. "
                                "Search operations may fail until index is queryable. "
                                "Consider increasing index_creation_timeout for large datasets."
                            )
                    else:
                        logger.info(
                            "Index creation initiated. Set wait_for_index_ready=True to block until ready. "
                            "Search operations may fail until index is queryable."
                        )
                    
                except PyMongoError as e:
                    # Handle race conditions where index is still dropping or other errors
                    logger.error(f"Error creating search index: {e}")
                    return collection

            return collection
        except PyMongoError as e:
            logger.error(f"Error creating collection and search index: {e}")
            return None

    def insert(
        self, vectors: List[List[float]], payloads: Optional[List[Dict]] = None, ids: Optional[List[str]] = None
    ) -> None:
        """
        Insert vectors into the collection.

        Args:
            vectors (List[List[float]]): List of vectors to insert.
            payloads (List[Dict], optional): List of payloads corresponding to vectors.
            ids (List[str], optional): List of IDs corresponding to vectors.
        """
        logger.info(f"Inserting {len(vectors)} vectors into collection '{self.collection_name}'.")

        data = []
        for vector, payload, _id in zip(vectors, payloads or [{}] * len(vectors), ids or [None] * len(vectors)):
            document = {"embedding": vector, "payload": payload}
            if _id:
                document["_id"] = _id
            data.append(document)
        try:
            if data:
                self.collection.insert_many(data)
                logger.info(f"Inserted {len(data)} documents into '{self.collection_name}'.")
        except PyMongoError as e:
            logger.error(f"Error inserting data: {e}")

    def search(self, query: str, vectors: List[float], limit=5, filters: Optional[Dict] = None) -> List[OutputData]:
        """
        Search for similar vectors using the vector search index.

        Args:
            query (str): Query string
            vectors (List[float]): Query vector.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search.

        Returns:
            List[OutputData]: Search results.
        """
        # Note: In high-throughput scenarios, consider caching index existence or handling the error gracefully
        # instead of checking on every search.
        
        results = []
        try:
            collection = self.client[self.db_name][self.collection_name]
            
            # Ensure numCandidates is significantly higher than limit for accuracy (HNSW)
            num_candidates = limit * 20

            pipeline = [
                {
                    "$vectorSearch": {
                        "index": self.index_name,
                        "limit": limit,
                        "numCandidates": num_candidates,
                        "queryVector": vectors,
                        "path": "embedding",
                    }
                },
                {"$set": {"score": {"$meta": "vectorSearchScore"}}},
                {"$project": {"embedding": 0}},
            ]

            # Add filter stage if filters are provided
            if filters:
                filter_conditions = []
                for key, value in filters.items():
                    filter_conditions.append({f"payload.{key}": value})

                if filter_conditions:
                    # Add a $match stage after vector search to apply filters
                    pipeline.insert(1, {"$match": {"$and": filter_conditions}})

            results = list(collection.aggregate(pipeline))
            logger.info(f"Vector search completed. Found {len(results)} documents.")
        except Exception as e:
            logger.error(f"Error during vector search for query {query}: {e}")
            return []

        output = [OutputData(id=str(doc["_id"]), score=doc.get("score"), payload=doc.get("payload")) for doc in results]
        return output

    def delete(self, vector_id: str) -> None:
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        try:
            result = self.collection.delete_one({"_id": vector_id})
            if result.deleted_count > 0:
                logger.info(f"Deleted document with ID '{vector_id}'.")
            else:
                logger.warning(f"No document found with ID '{vector_id}' to delete.")
        except PyMongoError as e:
            logger.error(f"Error deleting document: {e}")

    def update(self, vector_id: str, vector: Optional[List[float]] = None, payload: Optional[Dict] = None) -> None:
        """
        Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (List[float], optional): Updated vector.
            payload (Dict, optional): Updated payload.
        """
        update_fields = {}
        if vector is not None:
            update_fields["embedding"] = vector
        
        if payload is not None:
            for key, value in payload.items():
                update_fields[f"payload.{key}"] = value

        if update_fields:
            try:
                result = self.collection.update_one({"_id": vector_id}, {"$set": update_fields})
                if result.matched_count > 0:
                    logger.info(f"Updated document with ID '{vector_id}'.")
                else:
                    logger.warning(f"No document found with ID '{vector_id}' to update.")
            except PyMongoError as e:
                logger.error(f"Error updating document: {e}")

    def get(self, vector_id: str) -> Optional[OutputData]:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            Optional[OutputData]: Retrieved vector or None if not found.
        """
        try:
            doc = self.collection.find_one({"_id": vector_id})
            if doc:
                logger.info(f"Retrieved document with ID '{vector_id}'.")
                return OutputData(id=str(doc["_id"]), score=None, payload=doc.get("payload"))
            else:
                logger.warning(f"Document with ID '{vector_id}' not found.")
                return None
        except PyMongoError as e:
            logger.error(f"Error retrieving document: {e}")
            return None

    def list_cols(self) -> List[str]:
        """
        List all collections in the database.

        Returns:
            List[str]: List of collection names.
        """
        try:
            collections = self.db.list_collection_names()
            logger.info(f"Listing collections in database '{self.db_name}': {collections}")
            return collections
        except PyMongoError as e:
            logger.error(f"Error listing collections: {e}")
            return []

    def delete_col(self) -> None:
        """Delete the collection."""
        try:
            self.collection.drop()
            logger.info(f"Deleted collection '{self.collection_name}'.")
        except PyMongoError as e:
            logger.error(f"Error deleting collection: {e}")

    def col_info(self) -> Dict[str, Any]:
        """
        Get information about the collection.

        Returns:
            Dict[str, Any]: Collection information.
        """
        try:
            stats = self.db.command("collstats", self.collection_name)
            info = {"name": self.collection_name, "count": stats.get("count"), "size": stats.get("size")}
            logger.info(f"Collection info: {info}")
            return info
        except PyMongoError as e:
            logger.error(f"Error getting collection info: {e}")
            return {}

    def list(self, filters: Optional[Dict] = None, limit: int = 100) -> List[OutputData]:
        """
        List vectors in the collection.

        Args:
            filters (Dict, optional): Filters to apply to the list.
            limit (int, optional): Number of vectors to return.

        Returns:
            List[OutputData]: List of vectors.
        """
        try:
            query = {}
            if filters:
                # Apply filters to the payload field
                filter_conditions = []
                for key, value in filters.items():
                    filter_conditions.append({f"payload.{key}": value})
                if filter_conditions:
                    query = {"$and": filter_conditions}

            cursor = self.collection.find(query).limit(limit)
            results = [OutputData(id=str(doc["_id"]), score=None, payload=doc.get("payload")) for doc in cursor]
            logger.info(f"Retrieved {len(results)} documents from collection '{self.collection_name}'.")
            return results
        except PyMongoError as e:
            logger.error(f"Error listing documents: {e}")
            return []

    def reset(self):
        """Reset the index by deleting and recreating it."""
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.collection = self.create_col()

    def __del__(self) -> None:
        """Close the database connection when the object is deleted."""
        if hasattr(self, "client"):
            self.client.close()
            logger.info("MongoClient connection closed.")