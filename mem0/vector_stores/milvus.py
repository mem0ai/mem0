import logging
from typing import Dict, Optional

from pydantic import BaseModel

from mem0.configs.vector_stores.milvus import HybridSearchConfig, MetricType
from mem0.vector_stores.base import VectorStoreBase

try:
    import pymilvus  # noqa: F401
except ImportError:
    raise ImportError("The 'pymilvus' library is required. Please install it using 'pip install pymilvus'.")

from pymilvus import (
      CollectionSchema,
      DataType,
      FieldSchema,
      MilvusClient,
      Function,           # NEW
      FunctionType,       # NEW
      AnnSearchRequest,   # NEW
      RRFRanker,          # NEW
  )
logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # distance
    payload: Optional[Dict]  # metadata


class MilvusDB(VectorStoreBase):
    def __init__(
        self,
        url: str,
        token: str,
        collection_name: str,
        embedding_model_dims: int,
        metric_type: MetricType,
        db_name: str,
        hybrid_search: Optional[dict] = None
    ) -> None:
        """Initialize the MilvusDB database.

        Args:
            url (str): Full URL for Milvus/Zilliz server.
            token (str): Token/api_key for Zilliz server / for local setup defaults to None.
            collection_name (str): Name of the collection (defaults to mem0).
            embedding_model_dims (int): Dimensions of the embedding model (defaults to 1536).
            metric_type (MetricType): Metric type for similarity search (defaults to L2).
            db_name (str): Name of the database (defaults to "").
        """
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.metric_type = metric_type
        self.hybrid_search_config = None
        if hybrid_search:
            self.hybrid_search_config = HybridSearchConfig(**hybrid_search)
        self.client = MilvusClient(uri=url, token=token, db_name=db_name)
        self.create_col(
            collection_name=self.collection_name,
            vector_size=self.embedding_model_dims,
            metric_type=self.metric_type,
        )

    def create_col(
        self,
        collection_name: str,
        vector_size: int,
        metric_type: MetricType = MetricType.COSINE,
    ) -> None:
        """Create a new collection with index_type AUTOINDEX.

        Args:
            collection_name (str): Name of the collection (defaults to mem0).
            vector_size (int): Dimensions of the embedding model (defaults to 1536).
            metric_type (MetricType, optional): etric type for similarity search. Defaults to MetricType.COSINE.
        """

        if self.client.has_collection(collection_name):
            logger.info(f"Collection {collection_name} already exists. Skipping creation.")
        else:
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=512),
                FieldSchema(name="vectors", dtype=DataType.FLOAT_VECTOR, dim=vector_size),
                FieldSchema(name="metadata", dtype=DataType.JSON),
            ]
            functions = []
            if self.hybrid_search_config and self.hybrid_search_config.enabled:
                # Text field for BM25 input
                fields.append(
                    FieldSchema(
                        name="text",
                        dtype=DataType.VARCHAR,
                        max_length=self.hybrid_search_config.text_field_max_length,
                        enable_analyzer=True,
                        analyzer_params={"type": self.hybrid_search_config.analyzer_type}
                    )
                )
                # Sparse vector field for BM25 output
                fields.append(
                    FieldSchema(
                        name="sparse_vectors",
                        dtype=DataType.SPARSE_FLOAT_VECTOR
                    )
                )
                # BM25 function to auto-generate sparse vectors from text
                
                bm25_function = Function(
                    name="text_bm25_fn",
                    input_field_names=["text"],
                    output_field_names=["sparse_vectors"],
                    function_type=FunctionType.BM25
                )
                functions.append(bm25_function)

            schema = CollectionSchema(fields, enable_dynamic_field=True)
            
            for func in functions:
                schema.add_function(func)
            
            index_params = self.client.prepare_index_params()
            index_params.add_index(
                field_name="vectors",
                metric_type=str(metric_type),
                index_type="AUTOINDEX",
                index_name="vector_index"
            )
            if self.hybrid_search_config and self.hybrid_search_config.enabled:
                index_params.add_index(
                    field_name="sparse_vectors",
                    index_type="SPARSE_INVERTED_INDEX",
                    metric_type="BM25",
                    index_name="sparse_index"
                )
            self.client.create_collection(collection_name=collection_name, schema=schema, index_params=index_params)
            

    def insert(self, ids, vectors, payloads, **kwargs: Optional[dict[str, any]]):
        """Insert vectors into a collection.

        Args:
            vectors (List[List[float]]): List of vectors to insert.
            payloads (List[Dict], optional): List of payloads corresponding to vectors.
            ids (List[str], optional): List of IDs corresponding to vectors.
        """
        # Batch insert all records at once for better performance and consistency
        data = []
        for idx,embedding,metadata in zip(ids,vectors,payloads):
            record = { "id" : idx, "vectors" : embedding, "metadata" : metadata}
            
            if self.hybrid_search_config and self.hybrid_search_config.enabled:
                record["text"] = metadata.get("data","")
            data.append(record)

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

            uid = value.get("id")
            score = value.get("distance")
        
            entity = value.get("entity",{})
            metadata = entity.get("metadata") if entity else value.get("metadata")
            

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
        
        if self.hybrid_search_config and self.hybrid_search_config.enabled:
            return self._hybrid_search(query,vectors,limit,query_filter)
        else:
            return self._dense_search(vectors,limit,query_filter)

    
    def _dense_search(self,vectors:list,limit:int,query_filter:Optional[str]= None) -> list:
        """
        Standard dense vector search.
        
        Args:
            vectors (List[List[float]]): Query vectors.
            limit (int): Number of results to return.
            query_filter (str, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """
        hits = self.client.search(
            collection_name=self.collection_name,
            data=[vectors],
            limit=limit,
            filter=query_filter,
            output_fields=["*"]
        )
        return self._parse_output(data=hits[0])
        
    def _hybrid_search(self,query:str,vectors:list,limit:int,query_filter: Optional[str] = None) -> list:
        """
        Hybrid search using both dense and text vectors.
        
        Args:
            query (str): Text query.
            vectors (List[List[float]]): Dense vector query.
            limit (int): Number of results to return.
            query_filter (str, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """
        assert self.hybrid_search_config is not None 
        
        dense_req = AnnSearchRequest(
            data= [vectors],
            anns_field="vectors",
            param={"metric_type" : str(self.metric_type), "params" : {}},
            limit = limit,
            expr=query_filter
        )
        sparse_req = AnnSearchRequest(
            data=[query],
            anns_field="sparse_vectors",
            param={"metric_type" : "BM25", "params" : {}},
            limit = limit,
            expr=query_filter
        )
        
        reranker = RRFRanker(k=self.hybrid_search_config.rrf_k)
        hits = self.client.hybrid_search(
            collection_name=self.collection_name,
            reqs=[dense_req, sparse_req],
            ranker=reranker,
            limit=limit,
            output_fields=["*"]
        )
        
        return self._parse_output(data=hits[0])
        
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
        
        if self.hybrid_search_config and self.hybrid_search_config.enabled and payload:
            schema["text"] = payload.get("data","")
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

    def reset(self):
        """Reset the index by deleting and recreating it."""
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.create_col(self.collection_name, self.embedding_model_dims, self.metric_type)
