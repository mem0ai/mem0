import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
except ImportError:
    raise ImportError("The 'pymongo' library is required. Please install it using 'pip install pymongo'.")

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class DocumentDB(VectorStoreBase):
    VECTOR_TYPE = "vector"
    SIMILARITY_METRIC = "euclidean"

    def __init__(self, db_name: str, collection_name: str, embedding_model_dims: int, mongo_uri: str):
        """
        Initialize the DocumentDB vector store with vector search capabilities.

        Args:
            db_name (str): Database name
            collection_name (str): Collection name
            embedding_model_dims (int): Dimension of the embedding vector
            mongo_uri (str): DocumentDB connection URI
        """
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.db_name = db_name
        self.index_name = f"{collection_name}_vector_index"

        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.collection = self.create_col()

    def create_col(self):
        """Create new collection with vector index."""
        try:
            database = self.client[self.db_name]
            collection_names = database.list_collection_names()
            if self.collection_name not in collection_names:
                logger.info(f"Collection '{self.collection_name}' does not exist. Creating it now.")
                collection = database[self.collection_name]
                # Insert and remove a placeholder document to create the collection
                collection.insert_one({"_id": 0, "placeholder": True})
                collection.delete_one({"_id": 0})
                logger.info(f"Collection '{self.collection_name}' created successfully.")
            else:
                collection = database[self.collection_name]

            # Check if vector index already exists using list_indexes()
            existing_indexes = list(collection.list_indexes())
            vector_index_exists = any(idx.get("name") == self.index_name for idx in existing_indexes)
            
            if vector_index_exists:
                logger.info(f"Vector index '{self.index_name}' already exists in collection '{self.collection_name}'.")
            else:
                # Create vector index using DocumentDB syntax
                index_spec = {"vectorEmbedding": self.VECTOR_TYPE}
                index_options = {
                    "name": self.index_name,
                    "vectorOptions": {
                        "type": "hnsw",
                        "dimensions": self.embedding_model_dims,
                        "similarity": self.SIMILARITY_METRIC,
                        "m": 16,
                        "efConstruction": 64
                    }
                }
                
                collection.create_index(index_spec, **index_options)
                logger.info(
                    f"Vector index '{self.index_name}' created successfully for collection '{self.collection_name}'."
                )
            return collection
        except PyMongoError as e:
            logger.error(f"Error creating collection and vector index: {e}")
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
        for i, (vector, payload, _id) in enumerate(zip(vectors, payloads or [{}] * len(vectors), ids or [None] * len(vectors))):
            # Generate a unique ID if none provided
            if _id is None:
                import uuid
                _id = str(uuid.uuid4())
            document = {"_id": _id, "vectorEmbedding": vector, "payload": payload}
            data.append(document)
        try:
            self.collection.insert_many(data)
            logger.info(f"Inserted {len(data)} documents into '{self.collection_name}'.")
        except PyMongoError as e:
            logger.error(f"Error inserting data: {e}")

    def search(self, query: str, vectors: List[float], limit=5, filters: Optional[Dict] = None) -> List[OutputData]:
        """
        Search for similar vectors using DocumentDB vector search.

        Args:
            query (str): Query string
            vectors (List[float]): Query vector.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search.

        Returns:
            List[OutputData]: Search results.
        """

        # Check if vector index exists
        existing_indexes = list(self.collection.list_indexes())
        vector_index_exists = any(idx.get("name") == self.index_name for idx in existing_indexes)
        
        if not vector_index_exists:
            logger.error(f"Vector index '{self.index_name}' does not exist.")
            return []

        results = []
        try:
            collection = self.client[self.db_name][self.collection_name]
            
            # Simple DocumentDB vector search pipeline
            pipeline = [
                {
                    "$vectorSearch": {
                        "exact": False,
                        "index": self.index_name,
                        "limit": limit,
                        "path": "vectorEmbedding",
                        "queryVector": vectors,
                        "numCandidates": limit * 2,
                    }
                },
                {"$project": {"vectorEmbedding": 0}},
            ]

            # Add filter stage if filters are provided
            if filters:
                match_conditions = {}
                for key, value in filters.items():
                    match_conditions["payload." + key] = value
                
                if match_conditions:
                    pipeline.append({"$match": match_conditions})
            
            results = list(collection.aggregate(pipeline))
            logger.info(f"Vector search completed. Found {len(results)} documents.")
                    
        except Exception as e:
            logger.error(f"Error during vector search for query {query}: {e}")
            return []

        # DocumentDB doesn't return scores, use order-based scoring
        output = []
        for i, doc in enumerate(results):
            # Assign scores based on result order (1.0 for first, decreasing)
            score = max(0.1, 1.0 - (i * 0.05))
            output.append(OutputData(id=str(doc["_id"]), score=score, payload=doc.get("payload")))
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
            update_fields["vectorEmbedding"] = vector
        if payload is not None:
            update_fields["payload"] = payload

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
                for key, value in filters.items():
                    query["payload." + key] = value

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
            logger.info("DocumentDB connection closed.")
