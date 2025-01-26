import logging
from typing import List, Optional, Dict, Any, Callable

from pydantic import BaseModel

try:
    from pymongo.errors import PyMongoError
    from pymongo.operations import SearchIndexModel  

except ImportError:
    raise ImportError("The 'pymongo' library is required. Please install it using 'pip install pymongo'.")

from mem0.vector_stores.base import VectorStoreBase

from mdb_toolkit import CustomMongoClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class MongoVector(VectorStoreBase):
    def __init__(
        self,
        dbname: str,
        collection_name: str,
        embedding_model_dims: int,
        get_embedding: Callable[[str], List[float]],
        mdb_uri: str,
    ):
        """
        Initialize the MongoDB vector store with vector search capabilities.

        Args:
            dbname (str): Database name
            collection_name (str): Collection name
            embedding_model_dims (int): Dimension of the embedding vector
            get_embedding (callable): Function to compute embeddings
            mdb_uri (str): Full MongoDB URI for connection
        """
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims # not used
        self.dbname = dbname
        self.get_embedding = get_embedding

        # Use MongoDB URI directly
        self.client = CustomMongoClient(mdb_uri, get_embedding=get_embedding)

        self.db = self.client[dbname]
        self.collection = self.db[collection_name]

        # Create collection and indexes if they don't exist
        self.index_name = f"{collection_name}_vector_index"
        if not self.client.index_exists(dbname, collection_name, self.index_name):
            print("db name", dbname)
            print("collection name", collection_name)
            print("index name", self.index_name)
            self.client._create_search_index(
                dbname,
                collection_name,
                self.index_name,
                "cosine"
            )
            logger.info(
                f"Search index '{self.index_name}' created successfully "
                f"on '{dbname}.{collection_name}'."
            )
            # Wait for the search index to be READY
            logger.info("Waiting for the search index to be READY...")
            index_ready = self.client.wait_for_index_ready(
                database_name=dbname,
                collection_name=collection_name,
                index_name=self.index_name,
                max_attempts=10,
                wait_seconds=5
            )

            if index_ready:
                logger.info(f"Search index '{self.index_name}' is now READY and available!")
                print("Index is ready!")
            else:
                logger.error("Index creation process exceeded wait limit or failed.")
                print("Index creation process exceeded wait limit.")
                exit()

    def create_col(self, name: str, embedding_fn: Optional[Callable] = None) -> None:
        """
        Create a new collection if it doesn't exist.
        This method is required by the base class to avoid abstract instantiation errors.
        """
        self.client.create_if_not_exists(self.dbname, name)


    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None
    ):
        """
        Insert vectors into the collection.

        Args:
            vectors (List[List[float]]): List of vectors to insert.
            payloads (List[Dict], optional): List of payloads corresponding to vectors.
            ids (List[str], optional): List of IDs corresponding to vectors.
        """
        logger.info(f"Inserting {len(vectors)} vectors into collection '{self.collection_name}'.")

        data = []
        for vector, payload, _id in zip(vectors, payloads or [{}]*len(vectors), ids or [None]*len(vectors)):
            document = {
                "_id": _id,
                "id": _id,
                "embedding": vector,
                "payload": payload
            }
            data.append(document)

        try:
            self.collection.insert_many(data)
            logger.info(f"Inserted {len(data)} documents into '{self.collection_name}'.")
        except PyMongoError as e:
            logger.error(f"Error inserting data: {e}")

    def search(self, query: list, limit: int = 5, filters: dict = None) -> list:
        """
        Search for similar vectors using the vector search index.

        Args:
            query_vector (List[float]): Query vector.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search.

        Returns:
            List[OutputData]: Search results.
        """
        try:
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": self.index_name,
                        "limit": limit,
                        "numCandidates": limit,
                        "queryVector": query,
                        "path": "embedding",
                    }
                },
                {"$set": {"score": {"$meta": "vectorSearchScore"}}},
                {"$project": {"embedding": 0}},
            ]
            results = list(self.collection.aggregate(pipeline))
            logger.info(f"Vector search completed. Found {len(results)} documents.")
            logger.info(f"Search results: {results}")
            memory = []

            for value in results:
                uid, score, metadata = (
                    value.get("id"),
                    value.get("score"),
                    value.get("payload", {}),
                )

                memory_obj = OutputData(id=uid, score=score, payload=metadata)
                memory.append(memory_obj)

            return memory
        except Exception as e:
            logger.error(f"Error during vector search: {e}")
            return []

    def delete(self, vector_id: str):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        try:
            result = self.collection.delete_one({"id": vector_id})
            if result.deleted_count > 0:
                logger.info(f"Deleted document with ID '{vector_id}'.")
            else:
                logger.warning(f"No document found with ID '{vector_id}' to delete.")
        except PyMongoError as e:
            logger.error(f"Error deleting document: {e}")

    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None
    ):
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
            update_fields["payload"] = payload

        if update_fields:
            try:
                result = self.collection.update_one(
                    {"id": vector_id},
                    {"$set": update_fields}
                )
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
            doc = self.collection.find_one({"id": vector_id})
            if doc:
                logger.info(f"Retrieved document with ID '{vector_id}'.")
                return OutputData(
                    id=str(doc["id"]),
                    score=None,
                    payload=doc.get("payload")
                )
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
            logger.info(f"Listing collections in database '{self.dbname}': {collections}")
            return collections
        except PyMongoError as e:
            logger.error(f"Error listing collections: {e}")
            return []

    def delete_col(self):
        """
        Delete the collection.
        """
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
            info = {
                "name": self.collection_name,
                "count": stats.get("count"),
                "size": stats.get("size"),
            }
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
            query = filters or {}
            cursor = self.collection.find(query).limit(limit)
            results = [
                OutputData(
                    id=str(doc["id"]),
                    score=None,
                    payload=doc.get("payload")
                )
                for doc in cursor
            ]
            logger.info(f"Retrieved {len(results)} documents from collection '{self.collection_name}'.")
            return results
        except PyMongoError as e:
            logger.error(f"Error listing documents: {e}")
            return []

