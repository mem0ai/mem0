import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

try:
    from tcvectordb import RPCVectorDBClient
    from tcvectordb.exceptions import ServerInternalError
    from tcvectordb.model.enum import FieldType, IndexType, MetricType
    from tcvectordb.model.index import FilterIndex, VectorIndex
except ImportError:
    raise ImportError("The 'tcvectordb' library is required. Please install it using 'pip install tcvectordb'.")


logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # distance
    payload: Optional[Dict]  # metadata


DEFAULT_NO_NEED_INDEXED_FIELDS = ['data', 'hash', 'created_at', 'updated_at']


class TencentVectorDB(VectorStoreBase):

    def __init__(self,
                 url: str,
                 key: str,
                 username: Optional[str] = 'root',
                 database_name: Optional[str] = 'mem0',
                 collection_name: Optional[str] = 'mem0',
                 embedding_model_dims: Optional[int] = 1536,
                 metric_type: Optional[str] = 'COSINE',
                 index_type: Optional[str] = 'HNSW',
                 shard_num: Optional[int] = 2,
                 replica_num: Optional[int] = 2,
                 field_type: Optional[str] = 'vector',
                 params: Optional[Dict[str, Any]] = None,
                 no_index_fields: Optional[List[str]] = None,
                 ) -> None:
        """Initialize the TencentVectorDB database.

        Args:
            url (str): URL for TencentVectorDB instance.
            key (str): API key for TencentVectorDB instance.
            username (str, optional): Username for TencentVectorDB instance. Defaults to 'root'.
            database_name (str, optional): Name of the database. Defaults to 'mem0'.
            collection_name (str, optional): Name of the collection. Defaults to 'mem0'.
            embedding_model_dims (int, optional): Dimensions of the embedding model. Defaults to 1536.
            metric_type (str, optional): Metric type for similarity search. Defaults to 'COSINE'.
            index_type (str, optional): Index type for vectors. Defaults to 'HNSW'.
            shard_num (int, optional): Number of shards in the collection. Defaults to 2.
            replica_num (int, optional): Number of replicas for the collection. Defaults to 2.
            field_type (str, optional): Field type for the vector field. Defaults to 'vector'.
            params (Dict[str, Any], optional): Parameters for the index. Defaults to None.
            no_index_fields (List[str], optional): Fields that will not be indexed. Defaults to None.
        """
        self.database_name = database_name
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.client = RPCVectorDBClient(url=url, key=key, username=username)
        self.client.create_database_if_not_exists(database_name=self.database_name)
        self.no_index_fields = no_index_fields if no_index_fields else DEFAULT_NO_NEED_INDEXED_FIELDS
        self.create_col(
            name=self.collection_name,
            vector_size=embedding_model_dims,
            metric_type=metric_type,
            index_type=index_type,
            shard_num=shard_num,
            replica_num=replica_num,
            field_type=field_type,
            params=params,
        )

    def create_col(
        self,
        name: Optional[str] = 'mem0',
        vector_size: Optional[int] = 1536,
        metric_type: Optional[str] = "COSINE",
        index_type: Optional[str] = 'HNSW',
        shard_num: Optional[int] = 2,
        replica_num: Optional[int] = 2,
        field_type: Optional[str] = 'vector',
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Create a new collection with index_type AUTOINDEX.

        Args:
            name (str): Name of the collection (defaults to mem0).
            vector_size (int): Dimensions of the embedding model (defaults to 1536).
            metric_type (str, optional): metric type for similarity search. Defaults to 'COSINE'.
            index_type (str, optional): Index type for similarity search. Defaults to 'HNSW'.
            shard_num (int, optional): Number of shards. Defaults to 2.
            replica_num (int, optional): Number of replicas. Defaults to 2.
            field_type (str, optional): Field type for the vector field. Defaults to 'vector'.
            params (Dict[str, Any], optional): Parameters for the index. Defaults to None.
        """
        if not params:
            params = {
                "M": 16,
                "efConstruction": 200,
            }
        self.client.create_collection_if_not_exists(
            database_name=self.database_name,
            collection_name=name,
            shard=shard_num,
            replicas=replica_num,
            indexes=[
                FilterIndex(name='id', field_type=FieldType.String, index_type=IndexType.PRIMARY_KEY),
                VectorIndex(name='vector',
                            dimension=vector_size,
                            index_type=IndexType(index_type),
                            field_type=FieldType(field_type),
                            metric_type=MetricType(metric_type),
                            params=params),
                FilterIndex(name='metadata', field_type=FieldType.Json, index_type=IndexType.FILTER)
            ]
        )

    def _transform_payload(self, payload: dict) -> (dict, dict):
        """Move need indexed fields to metadata."""
        metadata = {}
        new_payload = {}
        if payload:
            for k, v in payload.items():
                if k in self.no_index_fields:
                    new_payload[k] = v
                else:
                    metadata[k] = v
        return metadata, new_payload

    def insert(self, vectors, payloads=None, ids=None):
        """Insert vectors into a collection.

        Args:
            vectors (List[List[float]]): List of vectors to insert.
            payloads (List[Dict], optional): List of payloads corresponding to vectors.
            ids (List[str], optional): List of IDs corresponding to vectors.
        """
        # Batch insert all records at once for better performance and consistency
        data = [
            {"id": idx, "vector": embedding, "metadata": metadata}
            for idx, embedding, metadata in zip(ids, vectors, payloads)
        ]
        for item in data:
            metadata, payload = self._transform_payload(item['metadata'])
            item['metadata'] = metadata
            item['payload'] = payload
        self.client.upsert(database_name=self.database_name,
                           collection_name=self.collection_name,
                           documents=data,
                           )

    def _create_filter(self, filters: dict):
        """Prepare filters for efficient query.

        Args:
            filters (dict): filters [user_id, agent_id, run_id]

        Returns:
            str: formated filter.
        """
        operands = []
        for key, value in filters.items():
            if isinstance(value, str):
                operands.append(f'metadata.{key} = "{value}"')
            else:
                operands.append(f'metadata.{key} = {value}')
        return " and ".join(operands)

    def _parse_output(self, data: list):
        """
        Parse the output data.

        Args:
            data (Dict): Output data.

        Returns:
            List[OutputData]: Parsed output data.
        """
        memory = []

        for value in data:
            uid, score, metadata, payload = (
                value.get("id"),
                value.get("score"),
                value.get("metadata", {}),
                value.get("payload", {}),
            )
            metadata.update(payload)
            memory_obj = OutputData(id=uid, score=score, payload=metadata)
            memory.append(memory_obj)

        return memory

    def search(self, query: str, vectors: list, limit: int = 5, filters: dict = None) -> list:
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
        query_filter = self._create_filter(filters) if filters else None
        try:
            hits = self.client.search(
                database_name=self.database_name,
                collection_name=self.collection_name,
                vectors=[vectors],
                limit=limit,
                filter=query_filter,
            )
        except ServerInternalError as e:
            if "Field Not Found" in e.message:
                return []
        result = self._parse_output(data=hits[0])
        return result

    def delete(self, vector_id):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        self.client.delete(database_name=self.database_name,
                           collection_name=self.collection_name,
                           document_ids=[vector_id],
                           )

    def update(self, vector_id=None, vector=None, payload=None):
        """
        Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (List[float], optional): Updated vector.
            payload (Dict, optional): Updated payload.
        """
        if not vector_id:
            return
        doc = self.get(vector_id).payload
        if payload:
            doc.update(payload)
        metadata, payload = self._transform_payload(doc)
        schema = {}
        if vector:
            schema["vector"] = vector
        if metadata:
            schema["metadata"] = metadata
        if payload:
            schema["payload"] = payload
        self.client.update(database_name=self.database_name,
                           collection_name=self.collection_name,
                           document_ids=[vector_id],
                           data=schema)

    def get(self, vector_id):
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector.
        """
        result = self.client.query(database_name=self.database_name,
                                   collection_name=self.collection_name,
                                   document_ids=[vector_id],
                                   )
        if not result:
            return None
        payload = result[0].get("payload", {})
        payload.update(result[0].get("metadata", {}))
        output = OutputData(
            id=result[0].get("id", None),
            score=result[0].get("score", None),
            payload=payload,
        )
        return output

    def list_cols(self):
        """
        List all collections.

        Returns:
            List[str]: List of collection names.
        """
        return self.client.list_collections(database_name=self.database_name)

    def delete_col(self):
        """Delete a collection."""
        return self.client.drop_collection(database_name=self.database_name, collection_name=self.collection_name)

    def col_info(self):
        """
        Get information about a collection.

        Returns:
            Dict[str, Any]: Collection information.
        """
        coll = self.client.describe_collection(database_name=self.database_name, collection_name=self.collection_name)
        return vars(coll)

    def list(self, filters: dict = None, limit: int = 100) -> list:
        """
        List all vectors in a collection.

        Args:
            filters (Dict, optional): Filters to apply to the list.
            limit (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            List[OutputData]: List of vectors.
        """
        query_filter = self._create_filter(filters) if filters else None
        try:
            result = self.client.query(database_name=self.database_name,
                                       collection_name=self.collection_name,
                                       filter=query_filter,
                                       limit=limit)
            memories = []
            for data in result:
                payload = data.get("payload", {})
                payload.update(data.get("metadata", {}))
                obj = OutputData(id=data.get("id"), score=data.get('score'), payload=payload)
                memories.append(obj)
            return [memories]
        except ServerInternalError as e:
            if "Field Not Found" in e.message:
                return []

    def reset(self):
        """Reset the index by deleting and recreating it."""
        logger.warning(f"Resetting index {self.collection_name}...")
        self.client.truncate_collection(database_name=self.database_name, collection_name=self.collection_name)
