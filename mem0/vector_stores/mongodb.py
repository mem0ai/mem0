import logging  
from typing import List, Optional, Dict, Any, Callable  
  
from pydantic import BaseModel  
  
try:  
    from pymongo.errors import PyMongoError  
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
        user: Optional[str] = None,  
        password: Optional[str] = None,  
        host: str = 'localhost',  
        port: int = 27017,  
    ):  
        """  
        Initialize the MongoDB vector store with vector search capabilities.  
  
        Args:  
            dbname (str): Database name  
            collection_name (str): Collection name  
            embedding_model_dims (int): Dimension of the embedding vector  
            get_embedding (callable): Function to compute embeddings  
            user (str, optional): Database user  
            password (str, optional): Database password  
            host (str, optional): Database host  
            port (int, optional): Database port  
        """  
        self.collection_name = collection_name  
        self.embedding_model_dims = embedding_model_dims  
        self.dbname = dbname  
        self.get_embedding = get_embedding  
  
        if user and password:  
            self.client = CustomMongoClient(  
                host=host,  
                port=port,  
                username=user,  
                password=password,  
                get_embedding=get_embedding  
            )  
        else:  
            self.client = CustomMongoClient(  
                host=host,  
                port=port,  
                get_embedding=get_embedding  
            )  
  
        self.db = self.client[dbname]  
        self.collection = self.db[collection_name]  
  
        # Create collection and indexes if they don't exist  
        self.client.create_if_not_exists(dbname, collection_name)  
        self.index_name = f"{collection_name}_vector_index"  
        if not self.client.index_exists(dbname, collection_name, self.index_name):   
            self._create_search_index(
                database_name=dbname,
                collection_name=collection_name,
                index_name=self.index_name,
                distance_metric="cosine",
            )
  
    def insert(self, vectors: List[List[float]], payloads: Optional[List[Dict]] = None, ids: Optional[List[str]] = None):  
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
                "embedding": vector,  
                "payload": payload  
            }  
            data.append(document)  
        try:  
            self.collection.insert_many(data)  
            logger.info(f"Inserted {len(data)} documents into '{self.collection_name}'.")  
        except PyMongoError as e:  
            logger.error(f"Error inserting data: {e}")  
  
    def search(self, query_vector: List[float], limit=5, filters: Optional[Dict] = None) -> List[OutputData]:  
        """  
        Search for similar vectors using the vector search index.  
  
        Args:  
            query_vector (List[float]): Query vector.  
            limit (int, optional): Number of results to return. Defaults to 5.  
            filters (Dict, optional): Filters to apply to the search.  
  
        Returns:  
            List[OutputData]: Search results.  
        """  
        results = []
        query_embedding = query_vector
        if not self.client.index_exists(self.dbname, self.collection_name, self.index_name):
            logger.error(f"Index '{index_name}' does not exist.")
            return []
        if query_embedding is None:
            logger.error(f"Failed to generate embedding for query: {query}")
            return []

        try:
            collection = self[database_name][collection_name]
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": index_name,
                        "limit": limit,
                        "numCandidates": limit,
                        "queryVector": query_embedding,
                        "path": "embedding",
                    }
                },
                {"$set": {"score": {"$meta": "vectorSearchScore"}}},
                {"$project": {"embedding": 0}},
            ]
            results = list(collection.aggregate(pipeline))
            logger.info(f"Vector search completed. Found {len(results)} documents.")
        except Exception as e:
            logger.error(f"Error during vector search: {e}")
            return []
  
        output = [OutputData(id=str(doc["_id"]), score=doc.get("score"), payload=doc.get("payload")) for doc in results]  
        return output  
  
    def delete(self, vector_id: str):  
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
  
    def update(self, vector_id: str, vector: Optional[List[float]] = None, payload: Optional[Dict] = None):  
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
                    {'_id': vector_id},  
                    {'$set': update_fields}  
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
            doc = self.collection.find_one({'_id': vector_id})  
            if doc:  
                logger.info(f"Retrieved document with ID '{vector_id}'.")  
                return OutputData(id=str(doc['_id']), score=None, payload=doc.get('payload'))  
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
            info = {  
                "name": self.collection_name,  
                "count": stats.get("count"),  
                "size": stats.get("size")  
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
            results = [OutputData(id=str(doc['_id']), score=None, payload=doc.get('payload')) for doc in cursor]  
            logger.info(f"Retrieved {len(results)} documents from collection '{self.collection_name}'.")  
            return results  
        except PyMongoError as e:  
            logger.error(f"Error listing documents: {e}")  
            return []  
  
    def __del__(self):  
        """Close the database connection when the object is deleted."""  
        if hasattr(self, "client"):  
            self.client.close()  
            logger.info("MongoClient connection closed.")  