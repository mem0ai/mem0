import logging
from typing import Dict, List, Optional

from pydantic import BaseModel

try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    raise ImportError("The 'chromadb' library is required. Please install it using 'pip install chromadb'.")

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # distance
    payload: Optional[Dict]  # metadata


class ChromaDB(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        client: Optional[chromadb.Client] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        path: Optional[str] = None,
        api_key: Optional[str] = None,
        tenant: Optional[str] = None,
    ):
        """
        Initialize the Chromadb vector store.

        Args:
            collection_name (str): Name of the collection.
            client (chromadb.Client, optional): Existing chromadb client instance. Defaults to None.
            host (str, optional): Host address for chromadb server. Defaults to None.
            port (int, optional): Port for chromadb server. Defaults to None.
            path (str, optional): Path for local chromadb database. Defaults to None.
            api_key (str, optional): ChromaDB Cloud API key. Defaults to None.
            tenant (str, optional): ChromaDB Cloud tenant ID. Defaults to None.
        """
        if client:
            self.client = client
        elif api_key and tenant:
            # Initialize ChromaDB Cloud client
            logger.info("Initializing ChromaDB Cloud client")
            self.client = chromadb.CloudClient(
                api_key=api_key,
                tenant=tenant,
                database="mem0"  # Use fixed database name for cloud
            )
        else:
            # Initialize local or server client
            self.settings = Settings(anonymized_telemetry=False)

            if host and port:
                self.settings.chroma_server_host = host
                self.settings.chroma_server_http_port = port
                self.settings.chroma_api_impl = "chromadb.api.fastapi.FastAPI"
            else:
                if path is None:
                    path = "db"

            self.settings.persist_directory = path
            self.settings.is_persistent = True

            self.client = chromadb.Client(self.settings)

        self.collection_name = collection_name
        self.collection = self.create_col(collection_name)

    def _parse_output(self, data: Dict) -> List[OutputData]:
        """
        Parse the output data.

        Args:
            data (Dict): Output data.

        Returns:
            List[OutputData]: Parsed output data.
        """
        keys = ["ids", "distances", "metadatas"]
        values = []

        for key in keys:
            value = data.get(key, [])
            if isinstance(value, list) and value and isinstance(value[0], list):
                value = value[0]
            values.append(value)

        ids, distances, metadatas = values
        max_length = max(len(v) for v in values if isinstance(v, list) and v is not None)

        result = []
        for i in range(max_length):
            entry = OutputData(
                id=ids[i] if isinstance(ids, list) and ids and i < len(ids) else None,
                score=(distances[i] if isinstance(distances, list) and distances and i < len(distances) else None),
                payload=(metadatas[i] if isinstance(metadatas, list) and metadatas and i < len(metadatas) else None),
            )
            result.append(entry)

        return result

    def create_col(self, name: str, embedding_fn: Optional[callable] = None):
        """
        Create a new collection.

        Args:
            name (str): Name of the collection.
            embedding_fn (Optional[callable]): Embedding function to use. Defaults to None.

        Returns:
            chromadb.Collection: The created or retrieved collection.
        """
        collection = self.client.get_or_create_collection(
            name=name,
            embedding_function=embedding_fn,
        )
        return collection

    def insert(
        self,
        vectors: List[list],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
    ):
        """
        Insert vectors into a collection.

        Args:
            vectors (List[list]): List of vectors to insert.
            payloads (Optional[List[Dict]], optional): List of payloads corresponding to vectors. Defaults to None.
            ids (Optional[List[str]], optional): List of IDs corresponding to vectors. Defaults to None.
        """
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")
        self.collection.add(ids=ids, embeddings=vectors, metadatas=payloads)

    def search(
        self, query: str, vectors: List[list], limit: int = 5, filters: Optional[Dict] = None
    ) -> List[OutputData]:
        """
        Search for similar vectors.

        Args:
            query (str): Query.
            vectors (List[list]): List of vectors to search.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Optional[Dict], optional): Filters to apply to the search. Defaults to None.

        Returns:
            List[OutputData]: Search results.
        """
        where_clause = self._generate_where_clause(filters) if filters else None
        results = self.collection.query(query_embeddings=vectors, where=where_clause, n_results=limit)
        final_results = self._parse_output(results)
        return final_results

    def delete(self, vector_id: str):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        self.collection.delete(ids=vector_id)

    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None,
    ):
        """
        Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (Optional[List[float]], optional): Updated vector. Defaults to None.
            payload (Optional[Dict], optional): Updated payload. Defaults to None.
        """
        self.collection.update(ids=vector_id, embeddings=vector, metadatas=payload)

    def get(self, vector_id: str) -> OutputData:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector.
        """
        result = self.collection.get(ids=[vector_id])
        return self._parse_output(result)[0]

    def list_cols(self) -> List[chromadb.Collection]:
        """
        List all collections.

        Returns:
            List[chromadb.Collection]: List of collections.
        """
        return self.client.list_collections()

    def delete_col(self):
        """
        Delete a collection.
        """
        self.client.delete_collection(name=self.collection_name)

    def col_info(self) -> Dict:
        """
        Get information about a collection.

        Returns:
            Dict: Collection information.
        """
        return self.client.get_collection(name=self.collection_name)

    def list(self, filters: Optional[Dict] = None, limit: int = 100) -> List[OutputData]:
        """
        List all vectors in a collection.

        Args:
            filters (Optional[Dict], optional): Filters to apply to the list. Defaults to None.
            limit (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            List[OutputData]: List of vectors.
        """
        where_clause = self._generate_where_clause(filters) if filters else None
        results = self.collection.get(where=where_clause, limit=limit)
        return [self._parse_output(results)]

    def reset(self):
        """Reset the index by deleting and recreating it."""
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.collection = self.create_col(self.collection_name)

    @staticmethod
    def _generate_where_clause(where: dict[str, any]) -> dict[str, any]:
        """
        Generate a properly formatted where clause for ChromaDB.
        
        Args:
            where (dict[str, any]): The filter conditions.
            
        Returns:
            dict[str, any]: Properly formatted where clause for ChromaDB.
        """
        if where is None:
            return {}
        
        def convert_condition(key: str, value: any) -> dict:
            """Convert universal filter format to ChromaDB format."""
            if value == "*":
                # Wildcard - match any value (ChromaDB doesn't have direct wildcard, so we skip this filter)
                return None
            elif isinstance(value, dict):
                # Handle comparison operators
                chroma_condition = {}
                for op, val in value.items():
                    if op == "eq":
                        chroma_condition[key] = {"$eq": val}
                    elif op == "ne":
                        chroma_condition[key] = {"$ne": val}
                    elif op == "gt":
                        chroma_condition[key] = {"$gt": val}
                    elif op == "gte":
                        chroma_condition[key] = {"$gte": val}
                    elif op == "lt":
                        chroma_condition[key] = {"$lt": val}
                    elif op == "lte":
                        chroma_condition[key] = {"$lte": val}
                    elif op == "in":
                        chroma_condition[key] = {"$in": val}
                    elif op == "nin":
                        chroma_condition[key] = {"$nin": val}
                    elif op in ["contains", "icontains"]:
                        # ChromaDB doesn't support contains, fallback to equality
                        chroma_condition[key] = {"$eq": val}
                    else:
                        # Unknown operator, treat as equality
                        chroma_condition[key] = {"$eq": val}
                return chroma_condition
            else:
                # Simple equality
                return {key: {"$eq": value}}
        
        processed_filters = []
        
        for key, value in where.items():
            if key == "$or":
                # Handle OR conditions
                or_conditions = []
                for condition in value:
                    or_condition = {}
                    for sub_key, sub_value in condition.items():
                        converted = convert_condition(sub_key, sub_value)
                        if converted:
                            or_condition.update(converted)
                    if or_condition:
                        or_conditions.append(or_condition)
                
                if len(or_conditions) > 1:
                    processed_filters.append({"$or": or_conditions})
                elif len(or_conditions) == 1:
                    processed_filters.append(or_conditions[0])
            
            elif key == "$not":
                # Handle NOT conditions - ChromaDB doesn't have direct NOT, so we'll skip for now
                continue
                
            else:
                # Regular condition
                converted = convert_condition(key, value)
                if converted:
                    processed_filters.append(converted)
        
        # Return appropriate format based on number of conditions
        if len(processed_filters) == 0:
            return {}
        elif len(processed_filters) == 1:
            return processed_filters[0]
        else:
            return {"$and": processed_filters}
