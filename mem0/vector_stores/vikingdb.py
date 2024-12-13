import logging
from typing import Dict, Optional, List, Any

from pydantic import BaseModel

from mem0.configs.vector_stores.milvus import MetricType
from mem0.vector_stores.base import VectorStoreBase

try:
    import volcengine  # noqa: F401
except ImportError:
    raise ImportError("The 'volcengine' library is required. Please install it using 'pip install volcengine'.")

from volcengine.viking_db import VikingDBService, Field, FieldType

logger = logging.getLogger(__name__)


# class OutputData(BaseModel):
#     id: Optional[str]  # memory id
#     score: Optional[float]  # distance
#     payload: Optional[Dict]  # metadata

class FieldConfig():
    @staticmethod
    def default_primary_fields() -> List[Field]:
        return [
            Field(field_name="id", field_type=FieldType.String, is_primary_key=True),
        ]
    
    @staticmethod
    def default_vector_fields(vector_size: int) -> List[Field]:
        return [
            Field(field_name="vectors", field_type=FieldType.Vector, dim=vector_size),
        ]
    
    @staticmethod
    def default_attrs_fields() -> List[Field]:
        return [
            Field(field_name="for_mem", field_type=FieldType.Bool, default_val=True),
            Field(field_name="extra", field_type=FieldType.String, default_val=""),
        ]
    
    @staticmethod
    def default_filtered_fields() -> List[Field]:
        return [
            Field(field_name="foreign_id", field_type=FieldType.List_String, default_val=[]),
            Field(field_name="status", field_type=FieldType.String, default_val=""),
            Field(field_name="public", field_type=FieldType.String, default_val=""),
            Field(field_name="create_ts", field_type=FieldType.Int64, default_val=0),
            Field(field_name="update_ts", field_type=FieldType.Int64, default_val=0),
            Field(field_name="invalidate_ts", field_type=FieldType.Int64, default_val=0),
            Field(field_name="pipeline", field_type=FieldType.String, default_val=""),
            Field(field_name="time_value", field_type=FieldType.Float32, default_val=1.0),
            Field(field_name="trust_value", field_type=FieldType.Float32, default_val=1.0),
        ]
    
    @staticmethod
    def default_partition_fields() -> List[Field]:
        return [Field(field_name="partition", field_type=FieldType.String, default_val="")]
    
    @staticmethod
    def default_metadata_fields() -> List[Field]:
        default_fields = []
        default_attrs_fields = Fields.default_attrs_fields()
        default_filtered_fields = Fields.default_filtered_fields()
        default_partition_fields = Fields.default_partition_fields()
        default_fields.extend(default_attrs_fields)
        default_fields.extend(default_filtered_fields)
        default_fields.extend(default_partition_fields)
        return default_fields

class IndexConfig():
    @staticmethod
    def default_index_name(collection_name: str) -> str:
        return f"{collection_name}_Index"
    
def default_index(
    collection_name: str, custom: Dict[str, Any] = {}, viking_db_service = None
) -> Index:
    filtered_fields = _default_filtered_fields()
    scalar_index = [field.field_name for field in filtered_fields]
    scalar_index.extend([field["name"] for field in custom.get("scalars", [])])
    partition_field = _default_partition_fields()[0]

    return Index(
        collection_name=collection_name,
        index_name=_default_index_name(collection_name),
        cpu_quota=custom.get("cpu_quota", 2),
        partition_by=partition_field.field_name,
        vector_index=custom.get(
            "vector_index",
            VectorIndexParams(
                distance=DistanceType.IP,
                index_type=IndexType.HNSW,
                quant=QuantType.Int8,
            ),
        ),
        scalar_index=scalar_index,
        shard_count=custom.get("shard_count", None),
        viking_db_service=viking_db_service,
        stat=None,
    )

class VikingDB(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        embedding_model_dims: int,
        metric_type: MetricType,
        ak: str,
        sk: str,
        host: str = "api-vikingdb.volces.com",
        region: str = "cn-beijing",
    ) -> None:
        """Initialize the VikingDB database.

        Args:
            collection_name (str): Name of the collection (defaults to mem0).
            embedding_model_dims (int): Dimensions of the embedding model (defaults to 2048).
            metric_type (MetricType): Metric type for similarity search (defaults to IP).
            ak (str): ACCESSKEY for authentication
            sk (str): SECRETKEY for authentication
            host (str): Host for VikingDB/ Volcengine server.
            region (str): Region for VikingDB server.
        """
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.metric_type = metric_type
        self.client = VikingDBService(host=host, region=region, ak=ak, sk=sk)
        self.create_col(
            collection_name=self.collection_name,
            vector_size=self.embedding_model_dims,
            metric_type=self.metric_type,
        )

    def create_col(
        self,
        collection_name: str,
        vector_size: str,
        metric_type: MetricType = MetricType.IP,
        # user_defined_scalar: List[Any] = [],
    ) -> None:
        """Create a new collection with index_type AUTOINDEX.

        Args:
            collection_name (str): Name of the collection (defaults to mem0).
            vector_size (str): Dimensions of the embedding model (defaults to 2048).
            metric_type (MetricType, optional): etric type for similarity search. Defaults to MetricType.IP.
        """
        
        if self.client.get_collection(collection_name) is not None:
            logger.info(f"Collection {collection_name} already exists. Skipping creation.")
        else:
            fields = FieldConfig.default_primary_fields() + FieldConfig.default_vector_fields(vector_size) + FieldConfig.default_metadata_fields()
            self.client.create_collection(collection_name=collection_name, fields=fields)
            self.client.create_index(collection_name=collection_name, index_name=IndexConfig.default_index_name(), )

    def insert(self, ids, vectors, payloads, **kwargs: Optional[dict[str, any]]):
        """Insert vectors into a collection.

        Args:
            vectors (List[List[float]]): List of vectors to insert.
            payloads (List[Dict], optional): List of payloads corresponding to vectors.
            ids (List[str], optional): List of IDs corresponding to vectors.
        """
        for idx, embedding, metadata in zip(ids, vectors, payloads):
            data = {"id": idx, "vectors": embedding, "metadata": metadata}
            self.client.insert(collection_name=self.collection_name, data=data, **kwargs)

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
                operands.append(f'(metadata["{key}"] == "{value}")')
            else:
                operands.append(f'(metadata["{key}"] == {value})')

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
            uid, score, metadata = (
                value.get("id"),
                value.get("distance"),
                value.get("entity", {}).get("metadata"),
            )

            memory_obj = OutputData(id=uid, score=score, payload=metadata)
            memory.append(memory_obj)

        return memory

    def search(self, query: list, limit: int = 5, filters: dict = None) -> list:
        """
        Search for similar vectors.

        Args:
            query (List[float]): Query vector.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """
        query_filter = self._create_filter(filters) if filters else None
        hits = self.client.search(
            collection_name=self.collection_name,
            data=[query],
            limit=limit,
            filter=query_filter,
            output_fields=["*"],
        )
        result = self._parse_output(data=hits[0])
        return result

    def delete(self, vector_id):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        self.client.delete(collection_name=self.collection_name, ids=vector_id)

    def update(self, vector_id=None, vector=None, payload=None):
        """
        Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (List[float], optional): Updated vector.
            payload (Dict, optional): Updated payload.
        """
        schema = {"id": vector_id, "vectors": vector, "metadata": payload}
        self.client.upsert(collection_name=self.collection_name, data=schema)

    def get(self, vector_id):
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector.
        """
        result = self.client.get(collection_name=self.collection_name, ids=vector_id)
        output = OutputData(
            id=result[0].get("id", None),
            score=None,
            payload=result[0].get("metadata", None),
        )
        return output

    def list_cols(self):
        """
        List all collections.

        Returns:
            List[str]: List of collection names.
        """
        return self.client.list_collections()

    def delete_col(self):
        """Delete a collection."""
        return self.client.drop_collection(collection_name=self.collection_name)

    def col_info(self):
        """
        Get information about a collection.

        Returns:
            Dict[str, Any]: Collection information.
        """
        return self.client.get_collection_stats(collection_name=self.collection_name)

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
        result = self.client.query(collection_name=self.collection_name, filter=query_filter, limit=limit)
        memories = []
        for data in result:
            obj = OutputData(id=data.get("id"), score=None, payload=data.get("metadata"))
            memories.append(obj)
        return [memories]
