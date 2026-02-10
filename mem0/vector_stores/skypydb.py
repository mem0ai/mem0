import logging
from typing import Dict, List, Optional

from pydantic import BaseModel

try:
    from skypydb.api.vector_client import VectorClient
except ImportError:
    raise ImportError("The 'skypydb' library is required. Please install it using 'pip install skypydb'.")

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # distance
    payload: Optional[Dict]  # metadata


class SkypyDB(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        client: Optional[VectorClient] = None,
        path: Optional[str] = None
    ):
        """
        Initialize the Skypydb vector store.

        Args:
            collection_name (str): Name of the collection.
            client (skypydb.Client, optional): Existing skypydb client instance. Defaults to None.
            path (str, optional): Path for local skypydb database. Defaults to None.
        """
        if client:
            self.client = client
        else:
            if path is None:
                path = "./db/_generated/mem0_vector.db"

            self.client = VectorClient(
                path=path
            )

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
        ids = data.get("ids", [])
        distances = data.get("distances", [])
        metadatas = data.get("metadatas", [])

        if ids and isinstance(ids[0], list):
            ids = ids[0]
        if distances and isinstance(distances[0], list):
            distances = distances[0]
        if metadatas and isinstance(metadatas[0], list):
            metadatas = metadatas[0]

        results = []
        for i in range(len(ids)):
            entry = OutputData(
                id=ids[i] if i < len(ids) else None,
                score=distances[i] if distances and i < len(distances) else None,
                payload=metadatas[i] if metadatas and i < len(metadatas) else None,
            )
            results.append(entry)

        return results

    def create_col(self, name: str):
        """
        Create a new collection.

        Args:
            name (str): Name of the collection.
            embedding_fn (Optional[callable]): Embedding function to use. Defaults to None.

        Returns:
            skypydb.Collection: The created or retrieved collection.
        """
        collection = self.client.get_or_create_collection(
            name=name
        )
        return collection

    def insert(
        self,
        vectors: List[List],
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
        # Handle case where vectors might be a single vector instead of list of vectors
        if vectors and not isinstance(vectors[0], list):
            vectors = [vectors]

        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in vectors]
        elif isinstance(ids, str):
            ids = [ids]

        if payloads is not None and not isinstance(payloads, list):
            payloads = [payloads]

        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")
        self.collection.add(ids=ids, embeddings=vectors, metadatas=payloads)

    def search(
        self,
        query: str,
        vectors: List[List],
        limit: int = 5,
        filters: Optional[Dict] = None,
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
        # Handle case where vectors might be a single vector
        if vectors and not isinstance(vectors[0], list):
            vectors = [vectors]

        where_clause = self._generate_where_clause(filters) if filters else None
        results = self.collection.query(
            query_embeddings=vectors,
            n_results=limit,
            where=where_clause,
        )
        final_results = self._parse_output(results)
        return final_results

    def delete(self, vector_id: str):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        self.collection.delete(ids=[vector_id])

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
        embeddings = None
        if vector is not None:
            # Ensure vector is wrapped in a list
            if not isinstance(vector[0], list):
                embeddings = [vector]
            else:
                embeddings = vector

        self.collection.update(
            ids=[vector_id],
            embeddings=embeddings,
            metadatas=[payload] if payload else None,
        )

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

    def list_cols(self) -> List:
        """
        List all collections.

        Returns:
            List[skypydb.Collection]: List of collections.
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
        return {"name": self.collection_name, "count": self.collection.count()}

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
        return self._parse_output(results)

    def reset(self):
        """
        Reset the index by deleting and recreating it.
        """
        
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.collection = self.create_col(self.collection_name)

    @staticmethod
    def _generate_where_clause(where: Optional[Dict]) -> Optional[Dict]:
        """
        Generate a properly formatted where clause for SkypyDB.
        
        Args:
            where (Optional[Dict]): The filter conditions.
            
        Returns:
           Optional[Dict]: Properly formatted where clause for SkypyDB.
        """
        if where is None:
            return None

        def convert_condition(key: str, value) -> Optional[Dict]:
            """
            Convert universal filter format to SkypyDB format.
            """

            if value == "*":
                # Wildcard - match any value (SkypyDB doesn't have direct wildcard, so we skip this filter)
                return None
            elif isinstance(value, dict):
                # Handle comparison operators
                result = {}
                for op, val in value.items():
                    if op == "eq":
                        result[key] = {"$eq": val}
                    elif op == "ne":
                        result[key] = {"$ne": val}
                    elif op == "gt":
                        result[key] = {"$gt": val}
                    elif op == "gte":
                        result[key] = {"$gte": val}
                    elif op == "lt":
                        result[key] = {"$lt": val}
                    elif op == "lte":
                        result[key] = {"$lte": val}
                    elif op == "in":
                        result[key] = {"$in": val}
                    elif op == "nin":
                        result[key] = {"$nin": val}
                    elif op in ["contains", "icontains"]:
                        # SkypyDB doesn't support contains, fallback to equality
                        result[key] = {"$eq": val}
                    else:
                        # Unknown operator, treat as equality
                        result[key] = {"$eq": val}
                return result
            else:
                # Simple equality
                return {key: {"$eq": value}}

        processed = []
        
        for key, value in where.items():
            if key == "$or":
                # Handle OR conditions
                or_conds = []
                for cond in value:
                    or_cond = {}
                    for sk, sv in cond.items():
                        conv = convert_condition(sk, sv)
                        if conv:
                            or_cond.update(conv)
                    if or_cond:
                        or_conds.append(or_cond)

                if len(or_conds) > 1:
                    processed.append({"$or": or_conds})
                elif or_conds:
                    processed.append(or_conds[0])

            elif key != "$not":
                # Handle NOT conditions
                conv = convert_condition(key, value)
                if conv:
                    processed.append(conv)

        # Return appropriate format based on number of conditions
        if len(processed) == 0:
            return {}
        elif len(processed) == 1:
            return processed[0]
        else:
            return {"$and": processed}
