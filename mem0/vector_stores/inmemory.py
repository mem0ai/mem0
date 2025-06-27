import logging
from typing import List, Optional

import numpy as np

from pydantic import BaseModel


from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class InMemory(VectorStoreBase):
    def __init__(
        self,
        collection_name,
    ):
        """
        Initialize the InMemory database.

        Args:
            collection_name (str): Collection name
        """
        self.collections = {}
        self.collection_name = collection_name
        self.create_col()

    def create_col(self):
        """
        Create a new collection (table in PostgreSQL).
        Will also initialize vector search index if specified.
        """
        self.collections[self.collection_name] = {}

    def insert(self, vectors, payloads=None, ids=None):
        """
        Insert vectors into a collection.

        Args:
            vectors (List[List[float]]): List of vectors to insert.
            payloads (List[Dict], optional): List of payloads corresponding to vectors.
            ids (List[str], optional): List of IDs corresponding to vectors.
        """
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")

        collection = self.collections[self.collection_name]
        for id, vector, payload in zip(ids, vectors, payloads):
            collection[id] = (vector, payload)

    def search(self, query, vectors, limit=5, filters=None):
        """
        Search for similar vectors.

        Args:
            query (str): Query.
            vectors (List[float]): Query vector.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """
        # FIXME: Filters
        # filter_conditions = []
        # filter_params = []
        #
        # if filters:
        #     for k, v in filters.items():
        #         filter_conditions.append("payload->>%s = %s")
        #         filter_params.extend([k, str(v)])
        #
        # filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""

        embedding = np.array(vectors, dtype=np.float32)
        results = []
        for id, (vector, payload) in self.collections[self.collection_name].items():
            np_vector = np.array(vector, dtype=np.float32)
            cos_sim = np.dot(embedding, np_vector) / np.linalg.norm(np_vector) / np.linalg.norm(embedding)
            distance = 1 - cos_sim
            output = OutputData(id=id, score=float(distance), payload=payload)
            results.append(output)

        return sorted(results, key=lambda r: r.score)[:limit]

    def delete(self, vector_id):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        self.collections[self.collection_name].pop(vector_id, None)

    def update(self, vector_id, vector=None, payload=None):
        """
        Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (List[float], optional): Updated vector.
            payload (Dict, optional): Updated payload.
        """

        self.collections[self.collection_name].update({vector_id: (vector, payload)})

    def get(self, vector_id) -> OutputData:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector.
        """

        result = self.collections[self.collection_name].get(vector_id, None)

        if result:
            (_vector, payload) = result
            return OutputData(id=vector_id, score=None, payload=payload)
        else:
            return None

    def list_cols(self) -> List[str]:
        """
        List all collections.

        Returns:
            List[str]: List of collection names.
        """
        return list(self.collections.keys())

    def delete_col(self):
        """Delete a collection."""
        self.collections.pop(self.collection_name, None)

    def col_info(self):
        """
        Get information about a collection.

        Returns:
            Dict[str, Any]: Collection information.
        """
        collection = self.collections[self.collection_name]

        # FIXME: "size"
        return {"name": self.collection_name, "count": len(collection), "size": "15Mb"}

    def list(self, filters=None, limit=100):
        """
        List all vectors in a collection.

        Args:
            filters (Dict, optional): Filters to apply to the list.
            limit (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            List[OutputData]: List of vectors.
        """
        # FIXME: Filters
        # filter_conditions = []
        # filter_params = []
        #
        # if filters:
        #     for k, v in filters.items():
        #         filter_conditions.append("payload->>%s = %s")
        #         filter_params.extend([k, str(v)])
        #
        # filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""

        results = self.collections[self.collection_name].items()

        if limit:
            results = results[:limit]

        return [[OutputData(id=id, score=None, payload=payload) for (id, (_vector, payload)) in results]]

    def __del__(self):
        pass

    def reset(self):
        """Reset the index by deleting and recreating it."""
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.create_col()
