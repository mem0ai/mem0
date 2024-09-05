from typing import Optional, List, Dict
from mem0.configs.vector_stores.milvus import MilvusDBConfig, MetricType
from pymilvus import MilvusClient, CollectionSchema, FieldSchema, DataType, Collection
from pydantic import BaseModel


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # distance
    payload: Optional[Dict]  # metadata



class MilvusDB():
    def __init__(self, url: str, token: str, collection_name: str, embedding_model_dims: int, metric_type: MetricType) -> None:
        
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.metric_type = metric_type
        
        self.client = MilvusClient(uri=url,token=token)
        
        self.create_col(
            collection_name=self.collection_name,
            vector_size=self.embedding_model_dims,
            metric_type=self.metric_type
        )
       
        
    def create_col(
        self, collection_name : str, vector_size : str, metric_type : MetricType = MetricType.COSINE
    ) -> None:

        if self.client.has_collection(collection_name):
            print(f"Collection {collection_name} already exists. Skipping creation.")
        else:
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=512),
                FieldSchema(name="vectors", dtype=DataType.FLOAT_VECTOR, dim=vector_size),
                FieldSchema(name="metadata", dtype=DataType.JSON),
            ]
            
            schema = CollectionSchema(fields, enable_dynamic_field=True)

            index = self.client.prepare_index_params(
                field_name="vectors",
                metric_type=metric_type,
                index_type="IVF_FLAT",
                index_name="vector_index",
                params={ "nlist": 128 }
            )
            
            self.client.create_collection(collection_name=collection_name, schema=schema, index_params=index)
            
            
    def insert(self, ids: list = None, vectors: list = None, payloads: list = None, **kwargs: Optional[dict[str, any]]):
        """Insert vectors into a collection."""
        for idx, embedding, metadata in zip(ids, vectors, payloads):
            data = {"id": idx, "vectors": embedding, "metadata": metadata}
            self.client.insert(collection_name=self.collection_name, data=data, **kwargs)


    def _create_filter(self, filters: dict):
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
                value.get("entity",{}).get("metadata")
            )
            
            memory_obj = OutputData(id=uid, score=score, payload=metadata)
            memory.append(memory_obj)

        return memory
        

    def search(self, query: list, limit: int = 5, filters: dict = None) -> list:
        """Search for similar vectors."""
        query_filter = self._create_filter(filters) if filters else None
        hits = self.client.search(
            collection_name=self.collection_name, 
            data=[query], limit=limit, filter=query_filter,
            output_fields=["*"]
        )
        result = self._parse_output(data=hits[0])
        
        return result
    
    def delete(self, vector_id):
        """Delete a vector by ID."""
        self.client.delete(collection_name=self.collection_name, ids=vector_id)
        

    def update(self, vector_id=None, vector=None, payload=None):
        """Update a vector and its payload."""
        schema = {"id" : vector_id, "vectors": vector, "metadata" : payload}
        self.client.upsert(collection_name=self.collection_name, data=schema)

    def get(self, vector_id):
        """Retrieve a vector by ID."""
        result = self.client.get(collection_name=self.collection_name, ids=vector_id)
        output = OutputData(id=result[0].get("id", None), score=None, payload=result[0].get("metadata", None))
        return output

    def list_cols(self):
        """List all collections."""
        return self.client.list_collections()

    def delete_col(self):
        """Delete a collection."""
        return self.client.drop_collection(collection_name=self.collection_name)

    def col_info(self):
        """Get information about a collection."""
        return self.client.get_collection_stats(collection_name=self.collection_name)

    def list(self, filters: dict = None, limit: int = 100) -> list:
        query_filter = self._create_filter(filters) if filters else None
        result = self.client.query(
                    collection_name=self.collection_name,
                    filter=query_filter,
                    limit=limit)
        memories = []
        for data in result:
            obj = OutputData(id=data.get("id"), score=None, payload=data.get("metadata"))
            memories.append(obj)
        return [memories]