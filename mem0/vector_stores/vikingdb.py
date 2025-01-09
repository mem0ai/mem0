import logging
import json
from typing import Dict, Optional, List, Any

from pydantic import BaseModel

from mem0.configs.vector_stores.vikingdb import MetricType, METRIC_TO_DISTANCE
from mem0.vector_stores.base import VectorStoreBase

try:
    from volcengine import viking_db  # noqa: F401
except ImportError:
    raise ImportError("The 'volcengine' library is required. Please install it using 'pip install volcengine'.")

from volcengine.viking_db import VikingDBService
from volcengine.viking_db import VectorIndexParams, Collection, Index, Data, ScalarOrder, Order, Field as VikingDBField, FieldType as VikingDBFieldType
from volcengine.viking_db.exception import CollectionNotExistException 

logger = logging.getLogger(__name__)

DEFAULT_ATTR_FIELDS = [
    VikingDBField(field_name="hash", field_type=VikingDBFieldType.String, default_val=""),
    VikingDBField(field_name="data", field_type=VikingDBFieldType.String, default_val=""),
    VikingDBField(field_name="metadata", field_type=VikingDBFieldType.String, default_val=""),
]

DEFAULT_FILTER_FIELDS = [
    VikingDBField(field_name="agent_id", field_type=VikingDBFieldType.String, default_val=""),
    VikingDBField(field_name="run_id", field_type=VikingDBFieldType.String, default_val=""),
    VikingDBField(field_name="user_id", field_type=VikingDBFieldType.String, default_val=""),
    VikingDBField(field_name="created_at", field_type=VikingDBFieldType.String, default_val=""),
    VikingDBField(field_name="updated_at", field_type=VikingDBFieldType.String, default_val=""),
]


excluded_keys = {"user_id", "agent_id", "run_id", "hash", "data", "created_at", "updated_at"}

class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # distance
    payload: Optional[Dict]  

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
        self.collection: Optional[Collection] = None
        self.index: Optional[Index] = None
        self.create_col(
            collection_name=self.collection_name,
            vector_size=self.embedding_model_dims,
            metric_type=self.metric_type,
        )
        
    def _has_collection(self):
        try:
            self.client.get_collection(self.collection_name)
        except CollectionNotExistException:
            return False
        
        return True
        
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
        if self._has_collection():
            self.collection = self.client.get_collection(self.collection_name)
            self.index = self.collection.indexes[0]
            logger.info(f"Collection {collection_name} already exists. Skipping creation.")
        else:
            fields = [
                VikingDBField(field_name="id", field_type=VikingDBFieldType.String, is_primary_key=True),
                VikingDBField(field_name="vectors", field_type=VikingDBFieldType.Vector, dim=vector_size),
            ]
            default_attr_fields = DEFAULT_ATTR_FIELDS.copy()
            default_filter_fields = DEFAULT_FILTER_FIELDS.copy()
            fields.extend(default_attr_fields)
            fields.extend(default_filter_fields)

            self.collection = self.client.create_collection(collection_name=collection_name, fields=fields)
            self.index = self.client.create_index(
                collection_name=collection_name, 
                index_name=f"{collection_name}_Index", 
                vector_index=VectorIndexParams(distance=METRIC_TO_DISTANCE[metric_type]),
                scalar_index=[field.field_name for field in default_filter_fields]
            )
    
    def _payload_to_fields(self, payload) -> Dict:
        excluded_fields = {k:v for k, v in payload.items() if k in excluded_keys}
        excluded_fields["metadata"] = json.dumps({k: v for k, v in payload.items() if k not in excluded_keys})
        return excluded_fields
    
    def _fields_to_payload(self, fields) -> Dict:
        excluded_fields = {k: fields[k] for k in excluded_keys}
        metadata = fields.get("metadata", "")
        excluded_fields["metadata"] = json.loads(metadata)
        return excluded_fields
    
    def insert(self, ids, vectors, payloads):
        """Insert vectors into a collection.

        Args:
            vectors (List[List[float]]): List of vectors to insert.
            payloads (List[Dict], optional): List of payloads corresponding to vectors.
            ids (List[str], optional): List of IDs corresponding to vectors.
        """
        data: List[Data] = []
        for idx, vector, payload in zip(ids, vectors, payloads):
            fields = {
                "id": idx, 
                "vectors": vector,
            }
            fields.update(
                self._payload_to_fields(payload)
            )
            data.append(Data(fields))
        self.collection.upsert_data(data)
        
    def _create_filter(self, filters: dict):
        """Prepare filters for efficient query.

        Args:
            filters (dict): filters [user_id, agent_id, run_id]

        Returns:
            dict: formated filter.
        """
        conds = []
        for k,v in filters.items():
            cond = { "op": "must", "field": k, "conds": v if isinstance(v, list) else [v]}
            conds.append(cond)
            
        dsl_filter = {
            "op": "and",
            "conds": conds,
        }
        return dsl_filter

    def _parse_output(self, data: List[Data]):
        """
        Parse the output data.

        Args:
            data (List[Data]): Output data.

        Returns:
            List[OutputData]: Parsed output data.
        """
        memory = []
        
        for value in data:
            fields = value.fields
            uid = fields.get('id')
            score = value.score
            payload = self._fields_to_payload(fields)
            memory_obj = OutputData(id=uid, score=score, payload=payload)
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
        data = self.index.search_by_vector(
            vector=query,
            filter=query_filter,
            limit=limit,
        )
        
        result = self._parse_output(data=data)
        return result

    def delete(self, vector_id):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        self.collection.delete_data(vector_id)

    def update(self, vector_id=None, vector=None, payload=None):
        """
        Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (List[float], optional): Updated vector.
            payload (Dict, optional): Updated payload.
        """
        fields = {"id": vector_id, "vectors": vector} #TODO None vector 
        fields.update(
            self._payload_to_fields(payload)
        )
        self.collection.upsert_data(data=Data(fields))
        return fields

    def get(self, vector_id):
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector.
        """
        result = self.collection.fetch_data(id=vector_id)
        output = self._parse_output([result])
        return output[0]

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
        return self.client.get_collection(collection_name=self.collection_name)

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
        data = self.index.search(order=ScalarOrder(field_name="create_ts", order=Order.Asc), filter=query_filter, limit=limit)
        result = self._parse_output(data=data)
        return result
