import logging
import time
import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel

try:
    from langchain_aws import NeptuneAnalyticsGraph
except ImportError:
    raise ImportError("langchain_aws is not installed. Please install it using pip install langchain_aws")

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # distance
    payload: Optional[Dict]  # metadata


class NeptuneAnalyticsVector(VectorStoreBase):
    """
    Neptune Analytics vector store implementation for Mem0.
    
    Provides vector storage and similarity search capabilities using Amazon Neptune Analytics,
    a serverless graph analytics service that supports vector operations.
    """

    _COLLECTION_PREFIX = "MEM0_VECTOR_"
    _FIELD_N = 'n'
    _FIELD_ID = '~id'
    _FIELD_PROP = '~properties'
    _FIELD_SCORE = 'score'
    _FIELD_LABEL = 'label'
    _TIMEZONE =  "UTC"

    def __init__(
        self,
        endpoint: str,
        collection_name: str,
    ):
        """
        Initialize the Neptune Analytics vector store.

        Args:
            endpoint (str): Neptune Analytics endpoint in format 'neptune-graph://<graphid>'.
            collection_name (str): Name of the collection to store vectors.
            
        Raises:
            ValueError: If endpoint format is invalid.
            ImportError: If langchain_aws is not installed.
        """

        if not endpoint.startswith("neptune-graph://"):
            raise ValueError("Please provide 'endpoint' with the format as 'neptune-graph://<graphid>'.")

        graph_id = endpoint.replace("neptune-graph://", "")
        self.graph = NeptuneAnalyticsGraph(graph_id)
        self.collection_name = self._COLLECTION_PREFIX + collection_name

    
    def create_col(self, name, vector_size, distance):
        """
        Create a collection (no-op for Neptune Analytics).
        
        Neptune Analytics supports dynamic indices that are created implicitly
        when vectors are inserted, so this method performs no operation.
        
        Args:
            name: Collection name (unused).
            vector_size: Vector dimension (unused).
            distance: Distance metric (unused).
        """
        pass

    
    def insert(self, vectors: List[list],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None):
        """
        Insert vectors into the collection.
        
        Creates or updates nodes in Neptune Analytics with vector embeddings and metadata.
        Uses MERGE operation to handle both creation and updates.
        
        Args:
            vectors (List[list]): List of embedding vectors to insert.
            payloads (Optional[List[Dict]]): Optional metadata for each vector.
            ids (Optional[List[str]]): Optional IDs for vectors. Generated if not provided.
        """

        para_list = []
        for index, data_vector in enumerate(vectors):
            if payloads:
                payload = payloads[index]
                payload[self._FIELD_LABEL] = self.collection_name
                payload["updated_at"] = str(int(time.time()))
            else:
                payload = {}
            para_list.append(dict(
                node_id=ids[index] if ids else str(uuid.uuid4()),
                properties=payload,
                embedding=data_vector,
            ))

        para_map_to_insert = {"rows": para_list}

        query_string = (f"""
            UNWIND $rows AS row
            MERGE (n :{self.collection_name} {{`~id`: row.node_id}})
            ON CREATE SET n = row.properties 
            ON MATCH SET n += row.properties 
        """
        )
        self.execute_query(query_string, para_map_to_insert)


        query_string_vector = (f"""
            UNWIND $rows AS row
            MATCH (n 
            :{self.collection_name}
             {{`~id`: row.node_id}})
            WITH n, row.embedding AS embedding
            CALL neptune.algo.vectors.upsert(n, embedding)
            YIELD success
            RETURN success
        """
        )
        result = self.execute_query(query_string_vector, para_map_to_insert)
        self._process_success_message(result, "Vector store - Insert")


    def search(
            self, query: str, vectors: List[float], limit: int = 5, filters: Optional[Dict] = None
    ) -> List[OutputData]:
        """
        Search for similar vectors using embedding similarity.
        
        Performs vector similarity search using Neptune Analytics' topKByEmbeddingWithFiltering
        algorithm to find the most similar vectors.
        
        Args:
            query (str): Search query text (unused in vector search).
            vectors (List[float]): Query embedding vector.
            limit (int, optional): Maximum number of results to return. Defaults to 5.
            filters (Optional[Dict]): Optional filters to apply to search results.
            
        Returns:
            List[OutputData]: List of similar vectors with scores and metadata.
        """

        if not filters:
            filters = {}
        filters[self._FIELD_LABEL] = self.collection_name

        filter_clause = self._get_node_filter_clause(filters)

        query_string = f"""
            CALL neptune.algo.vectors.topKByEmbeddingWithFiltering({{
                    topK: {limit},
                    embedding: {vectors}
                    {filter_clause}
                  }}
                )
            YIELD node, score
            RETURN node as n, score
            """
        query_response = self.execute_query(query_string)
        if len(query_response) > 0:
            return self._parse_query_responses(query_response, with_score=True)
        else :
            return []

    
    def delete(self, vector_id: str):
        """
        Delete a vector by its ID.
        
        Removes the node and all its relationships from the Neptune Analytics graph.
        
        Args:
            vector_id (str): ID of the vector to delete.
        """
        params = dict(node_id=vector_id)
        query_string = f"""
            MATCH (n :{self.collection_name}) 
            WHERE id(n) = $node_id 
            DETACH DELETE n
        """
        self.execute_query(query_string, params)

    def update(
            self,
            vector_id: str,
            vector: Optional[List[float]] = None,
            payload: Optional[Dict] = None,
    ):
        """
        Update a vector's embedding and/or metadata.
        
        Updates the node properties and/or vector embedding for an existing vector.
        Can update either the payload, the vector, or both.
        
        Args:
            vector_id (str): ID of the vector to update.
            vector (Optional[List[float]]): New embedding vector.
            payload (Optional[Dict]): New metadata to replace existing payload.
        """

        if payload:
            # Replace payload
            payload[self._FIELD_LABEL] = self.collection_name
            payload["updated_at"] = str(int(time.time()))
            para_payload = {
                "properties": payload,
                "vector_id": vector_id
            }
            query_string_embedding = f"""
            MATCH (n :{self.collection_name}) 
                WHERE id(n) = $vector_id 
                SET n = $properties       
            """
            self.execute_query(query_string_embedding, para_payload)

        if vector:
            para_embedding = {
                "embedding": vector,
                "vector_id": vector_id
            }
            query_string_embedding = f"""
            MATCH (n :{self.collection_name}) 
                WHERE id(n) = $vector_id 
            WITH $embedding as embedding, n as n    
            CALL neptune.algo.vectors.upsert(n, embedding) 
            YIELD success 
            RETURN success       
            """
            self.execute_query(query_string_embedding, para_embedding)


    
    def get(self, vector_id: str):
        """
        Retrieve a vector by its ID.
        
        Fetches the node data including metadata for the specified vector ID.
        
        Args:
            vector_id (str): ID of the vector to retrieve.
            
        Returns:
            OutputData: Vector data with metadata, or None if not found.
        """
        params = dict(node_id=vector_id)
        query_string = f"""
            MATCH (n :{self.collection_name}) 
            WHERE id(n) = $node_id 
            RETURN n
        """

        # Composite the query
        result = self.execute_query(query_string, params)

        if len(result) != 0:
            return self._parse_query_responses(result)[0]


    def list_cols(self):
        """
        List all collections with the Mem0 prefix.
        
        Queries the Neptune Analytics schema to find all node labels that start
        with the Mem0 collection prefix.
        
        Returns:
            List[str]: List of collection names.
        """
        query_string = f"""
        CALL neptune.graph.pg_schema() 
        YIELD schema 
        RETURN [ label IN schema.nodeLabels WHERE label STARTS WITH '{self.collection_name}'] AS result 
        """
        result = self.execute_query(query_string)
        if len(result) == 1 and "result" in result[0]:
            return result[0]["result"]
        else:
            return []


    def delete_col(self):
        """
        Delete the entire collection.
        
        Removes all nodes with the collection label and their relationships
        from the Neptune Analytics graph.
        """
        self.execute_query(f"MATCH (n :{self.collection_name}) DETACH DELETE n")


    def col_info(self):
        """
        Get collection information (no-op for Neptune Analytics).
        
        Collections are created dynamically in Neptune Analytics, so no
        collection-specific metadata is available.
        """
        pass


    def list(self, filters: Optional[Dict] = None, limit: int = 100) -> List[OutputData]:
        """
        List all vectors in the collection with optional filtering.
        
        Retrieves vectors from the collection, optionally filtered by metadata properties.
        
        Args:
            filters (Optional[Dict]): Optional filters to apply based on metadata.
            limit (int, optional): Maximum number of vectors to return. Defaults to 100.
            
        Returns:
            List[OutputData]: List of vectors with their metadata.
        """
        where_clause = self._get_where_clause(filters) if filters else ""

        para = {
            "limit": limit,
        }
        query_string = f"""
            MATCH (n :{self.collection_name})
            {where_clause}
            RETURN n
            LIMIT $limit
        """
        query_response = self.execute_query(query_string, para)

        if len(query_response) > 0:
            # Handle if there is no match.
            return [self._parse_query_responses(query_response)]
        return [[]]

    
    def reset(self):
        """
        Reset the collection by deleting all vectors.
        
        Removes all vectors from the collection, effectively resetting it to empty state.
        """
        self.delete_col()


    def _parse_query_responses(self, response: dict, with_score: bool = False):
        """
        Parse Neptune Analytics query responses into OutputData objects.
        
        Args:
            response (dict): Raw query response from Neptune Analytics.
            with_score (bool, optional): Whether to include similarity scores. Defaults to False.
            
        Returns:
            List[OutputData]: Parsed response data.
        """
        result = []
        # Handle if there is no match.
        for item in response:
            id = item[self._FIELD_N][self._FIELD_ID]
            properties = item[self._FIELD_N][self._FIELD_PROP]
            properties.pop("label", None)
            if with_score:
                score = item[self._FIELD_SCORE]
            else:
                score = None
            result.append(OutputData(
                id=id,
                score=score,
                payload=properties,
            ))
        return result


    def execute_query(self, query_string: str, params=None):
        """
        Execute an openCypher query on Neptune Analytics.
        
        This is a wrapper method around the Neptune Analytics graph query execution
        that provides debug logging for query monitoring and troubleshooting.
        
        Args:
            query_string (str): The openCypher query string to execute.
            params (dict): Parameters to bind to the query.
            
        Returns:
            Query result from Neptune Analytics graph execution.
        """
        if params is None:
            params = {}
        logger.debug(f"Executing openCypher query:[{query_string}], with parameters:[{params}].")
        return self.graph.query(query_string, params)


    @staticmethod
    def _get_where_clause(filters: dict):
        """
        Build WHERE clause for Cypher queries from filters.
        
        Args:
            filters (dict): Filter conditions as key-value pairs.
            
        Returns:
            str: Formatted WHERE clause for Cypher query.
        """
        where_clause = ""
        for i, (k, v) in enumerate(filters.items()):
            if i == 0:
                where_clause += f"WHERE n.{k} = '{v}' "
            else:
                where_clause += f"AND n.{k} = '{v}' "
        return where_clause

    @staticmethod
    def _get_node_filter_clause(filters: dict):
        """
        Build node filter clause for vector search operations.

        Creates filter conditions for Neptune Analytics vector search operations
        using the nodeFilter parameter format.

        Args:
            filters (dict): Filter conditions as key-value pairs.

        Returns:
            str: Formatted node filter clause for vector search.
        """
        conditions = []
        for k, v in filters.items():
            conditions.append(f"{{equals:{{property: '{k}', value: '{v}'}}}}")

        if len(conditions) == 1:
            filter_clause = f", nodeFilter: {conditions[0]}"
        else:
            filter_clause = f"""
                      , nodeFilter: {{andAll: [ {", ".join(conditions)} ]}} 
                  """
        return filter_clause


    @staticmethod
    def _process_success_message(response, context):
        """
        Process and validate success messages from Neptune Analytics operations.

        Checks the response from vector operations (insert/update) to ensure they
        completed successfully. Logs errors if operations fail.

        Args:
            response: Response from Neptune Analytics vector operation.
            context (str): Context description for logging (e.g., "Vector store - Insert").
        """
        for success_message in response:
            if "success" not in success_message:
                logger.error(f"Query execution status is absent on action:  [{context}]")
                break

            if success_message["success"] is not True:
                logger.error(f"Abnormal response status on action: [{context}] with message: [{success_message['success']}] ")
                break
