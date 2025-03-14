import logging
import traceback
import uuid
from typing import Any, Dict, List, Optional, Tuple

import google.api_core.exceptions
from google.cloud import aiplatform, aiplatform_v1
from google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint import (
    Namespace,
)
from google.oauth2 import service_account
from langchain.schema import Document
from pydantic import BaseModel

from mem0.configs.vector_stores.vertex_ai_vector_search import (
    GoogleMatchingEngineConfig,
)
from mem0.vector_stores.base import VectorStoreBase

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # distance
    payload: Optional[Dict]  # metadata


class GoogleMatchingEngine(VectorStoreBase):
    def __init__(self, **kwargs):
        """Initialize Google Matching Engine client."""
        logger.debug("Initializing Google Matching Engine with kwargs: %s", kwargs)
        
        # If collection_name is passed, use it as deployment_index_id if deployment_index_id is not provided
        if 'collection_name' in kwargs and 'deployment_index_id' not in kwargs:
            kwargs['deployment_index_id'] = kwargs['collection_name']
            logger.debug("Using collection_name as deployment_index_id: %s", kwargs['deployment_index_id'])
        elif 'deployment_index_id' in kwargs and 'collection_name' not in kwargs:
            kwargs['collection_name'] = kwargs['deployment_index_id']
            logger.debug("Using deployment_index_id as collection_name: %s", kwargs['collection_name'])
        
        try:
            config = GoogleMatchingEngineConfig(**kwargs)
            logger.debug("Config created: %s", config.model_dump())
            logger.debug("Config collection_name: %s", getattr(config, 'collection_name', None))
        except Exception as e:
            logger.error("Failed to validate config: %s", str(e))
            raise

        self.project_id = config.project_id
        self.project_number = config.project_number
        self.region = config.region
        self.endpoint_id = config.endpoint_id
        self.index_id = config.index_id  # The actual index ID
        self.deployment_index_id = config.deployment_index_id  # The deployment-specific ID
        self.collection_name = config.collection_name
        self.vector_search_api_endpoint = config.vector_search_api_endpoint
        
        logger.debug("Using project=%s, location=%s", self.project_id, self.region)
        
        # Initialize Vertex AI with credentials if provided
        init_args = {
            "project": self.project_id,
            "location": self.region,
        }
        if hasattr(config, 'credentials_path') and config.credentials_path:
            logger.debug("Using credentials from: %s", config.credentials_path)
            credentials = service_account.Credentials.from_service_account_file(
                config.credentials_path
            )
            init_args["credentials"] = credentials
        
        try:
            aiplatform.init(**init_args)
            logger.debug("Vertex AI initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize Vertex AI: %s", str(e))
            raise
        
        try:
            # Format the index path properly using the configured index_id
            index_path = f"projects/{self.project_number}/locations/{self.region}/indexes/{self.index_id}"
            logger.debug("Initializing index with path: %s", index_path)
            self.index = aiplatform.MatchingEngineIndex(index_name=index_path)
            logger.debug("Index initialized successfully")
            
            # Format the endpoint name properly
            endpoint_name = self.endpoint_id
            logger.debug("Initializing endpoint with name: %s", endpoint_name)
            self.index_endpoint = aiplatform.MatchingEngineIndexEndpoint(
                index_endpoint_name=endpoint_name
            )
            logger.debug("Endpoint initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize Matching Engine components: %s", str(e))
            raise ValueError(f"Invalid configuration: {str(e)}")

    def _parse_output(self, data: Dict) -> List[OutputData]:
        """
        Parse the output data.
        Args:
            data (Dict): Output data.
        Returns:
            List[OutputData]: Parsed output data.
        """
        results = data.get("nearestNeighbors", {}).get("neighbors", [])
        output_data = []
        for result in results:
            output_data.append(
                OutputData(
                    id=result.get("datapoint").get("datapointId"),
                    score=result.get("distance"),
                    payload=result.get("datapoint").get("metadata"),
                )
            )
        return output_data

    def _create_restriction(self, key: str, value: Any) -> aiplatform_v1.types.index.IndexDatapoint.Restriction:
        """Create a restriction object for the Matching Engine index.
        
        Args:
            key: The namespace/key for the restriction
            value: The value to restrict on
        
        Returns:
            Restriction object for the index
        """
        str_value = str(value) if value is not None else ""
        return aiplatform_v1.types.index.IndexDatapoint.Restriction(
            namespace=key,
            allow_list=[str_value]
        )

    def _create_datapoint(
        self, 
        vector_id: str, 
        vector: List[float], 
        payload: Optional[Dict] = None
    ) -> aiplatform_v1.types.index.IndexDatapoint:
        """Create a datapoint object for the Matching Engine index.
        
        Args:
            vector_id: The ID for the datapoint
            vector: The vector to store
            payload: Optional metadata to store with the vector
        
        Returns:
            IndexDatapoint object
        """
        restrictions = []
        if payload:
            restrictions = [
                self._create_restriction(key, value) 
                for key, value in payload.items()
            ]
        
        return aiplatform_v1.types.index.IndexDatapoint(
            datapoint_id=vector_id,
            feature_vector=vector,
            restricts=restrictions
        )

    def insert(
        self,
        vectors: List[list],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
    ) -> None:
        """Insert vectors into the Matching Engine index.
        
        Args:
            vectors: List of vectors to insert
            payloads: Optional list of metadata dictionaries
            ids: Optional list of IDs for the vectors
            
        Raises:
            ValueError: If vectors is empty or lengths don't match
            GoogleAPIError: If the API call fails
        """
        if not vectors:
            raise ValueError("No vectors provided for insertion")
        
        if payloads and len(payloads) != len(vectors):
            raise ValueError(f"Number of payloads ({len(payloads)}) does not match number of vectors ({len(vectors)})")
        
        if ids and len(ids) != len(vectors):
            raise ValueError(f"Number of ids ({len(ids)}) does not match number of vectors ({len(vectors)})")
        
        logger.debug("Starting insert of %d vectors", len(vectors))
        
        try:
            datapoints = [
                self._create_datapoint(
                    vector_id=ids[i] if ids else str(uuid.uuid4()),
                    vector=vector,
                    payload=payloads[i] if payloads and i < len(payloads) else None
                )
                for i, vector in enumerate(vectors)
            ]
            
            logger.debug("Created %d datapoints", len(datapoints))
            self.index.upsert_datapoints(datapoints=datapoints)
            logger.debug("Successfully inserted datapoints")
            
        except google.api_core.exceptions.GoogleAPIError as e:
            logger.error("Failed to insert vectors: %s", str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error during insert: %s", str(e))
            logger.error("Stack trace: %s", traceback.format_exc())
            raise


    def search(self, query: List[float], limit: int = 5, filters: Optional[Dict] = None) -> List[OutputData]:
        """
        Search for similar vectors.
        Args:
            query (List[float]): Query vector.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Optional[Dict], optional): Filters to apply to the search. Defaults to None.
        Returns:
            List[OutputData]: Search results (unwrapped)
        """
        logger.debug("Starting search")
        logger.debug("Query type: %s, length: %d", type(query), len(query))
        logger.debug("Limit: %d, Filters: %s", limit, filters)
        
        try:
            filter_namespaces = []
            if filters:
                logger.debug("Processing filters")
                for key, value in filters.items():
                    logger.debug("Processing filter %s=%s (type=%s)", key, value, type(value))
                    if isinstance(value, (str, int, float)):
                        logger.debug("Adding simple filter for %s", key)
                        filter_namespaces.append(
                            Namespace(key, [str(value)], [])
                        )
                    elif isinstance(value, dict):
                        logger.debug("Adding complex filter for %s", key)
                        includes = value.get('include', [])
                        excludes = value.get('exclude', [])
                        filter_namespaces.append(
                            Namespace(key, includes, excludes)
                        )
            
            logger.debug("Final filter_namespaces: %s", filter_namespaces)
            
            response = self.index_endpoint.find_neighbors(
                deployed_index_id=self.deployment_index_id,
                queries=[query],
                num_neighbors=limit,
                filter=filter_namespaces if filter_namespaces else None,
                return_full_datapoint=True
            )
            
            if not response or len(response) == 0 or len(response[0]) == 0:
                logger.debug("No results found")
                return []
            
            results = []
            for neighbor in response[0]:
                logger.debug("Processing neighbor - id: %s, distance: %s", 
                            neighbor.id, neighbor.distance)
                
                payload = {}
                if hasattr(neighbor, 'restricts'):
                    logger.debug("Processing restricts")
                    for restrict in neighbor.restricts:
                        if (hasattr(restrict, 'name') and 
                            hasattr(restrict, 'allow_tokens') and 
                            restrict.allow_tokens):
                            logger.debug("Adding %s: %s", restrict.name, restrict.allow_tokens[0])
                            payload[restrict.name] = restrict.allow_tokens[0]
                
                output_data = OutputData(
                    id=neighbor.id,
                    score=neighbor.distance,
                    payload=payload
                )
                results.append(output_data)
            
            logger.debug("Returning %d results", len(results))
            return results

        except Exception as e:
            logger.error("Error occurred: %s", str(e))
            logger.error("Error type: %s", type(e))
            logger.error("Stack trace: %s", traceback.format_exc())
            raise


    def delete(self, vector_id: Optional[str] = None, ids: Optional[List[str]] = None) -> bool:
        """
        Delete vectors from the Matching Engine index.
        Args:
            vector_id (Optional[str]): Single ID to delete (for backward compatibility)
            ids (Optional[List[str]]): List of IDs of vectors to delete
        Returns:
            bool: True if vectors were deleted successfully or already deleted, False if error
        """
        logger.debug("Starting delete, vector_id: %s, ids: %s", vector_id, ids)
        try:
            # Handle both single vector_id and list of ids
            if vector_id:
                datapoint_ids = [vector_id]
            elif ids:
                datapoint_ids = ids
            else:
                raise ValueError("Either vector_id or ids must be provided")

            logger.debug("Deleting ids: %s", datapoint_ids)
            try:
                self.index.remove_datapoints(datapoint_ids=datapoint_ids)
                logger.debug("Delete completed successfully")
                return True
            except google.api_core.exceptions.NotFound:
                # If the datapoint is already deleted, consider it a success
                logger.debug("Datapoint already deleted")
                return True
            except google.api_core.exceptions.PermissionDenied as e:
                logger.error("Permission denied: %s", str(e))
                return False
            except google.api_core.exceptions.InvalidArgument as e:
                logger.error("Invalid argument: %s", str(e))
                return False
            
        except Exception as e:
            logger.error("Error occurred: %s", str(e))
            logger.error("Error type: %s", type(e))
            logger.error("Stack trace: %s", traceback.format_exc())
            return False


    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None,
    ) -> bool:
        """Update a vector and its payload.
        
        Args:
            vector_id: ID of the vector to update
            vector: Optional new vector values
            payload: Optional new metadata payload
            
        Returns:
            bool: True if update was successful
            
        Raises:
            ValueError: If neither vector nor payload is provided
            GoogleAPIError: If the API call fails
        """
        logger.debug("Starting update for vector_id: %s", vector_id)
        
        if vector is None and payload is None:
            raise ValueError("Either vector or payload must be provided for update")
        
        # First check if the vector exists
        try:
            existing = self.get(vector_id)
            if existing is None:
                logger.error("Vector ID not found: %s", vector_id)
                return False
            
            datapoint = self._create_datapoint(
                vector_id=vector_id,
                vector=vector if vector is not None else [],
                payload=payload
            )
            
            logger.debug("Upserting datapoint: %s", datapoint)
            self.index.upsert_datapoints(datapoints=[datapoint])
            logger.debug("Update completed successfully")
            return True
            
        except google.api_core.exceptions.GoogleAPIError as e:
            logger.error("API error during update: %s", str(e))
            return False
        except Exception as e:
            logger.error("Unexpected error during update: %s", str(e))
            logger.error("Stack trace: %s", traceback.format_exc())
            raise


    def get(self, vector_id: str) -> Optional[OutputData]:
        """
        Retrieve a vector by ID.
        Args:
            vector_id (str): ID of the vector to retrieve.
        Returns:
            Optional[OutputData]: Retrieved vector or None if not found.
        """
        logger.debug("Starting get for vector_id: %s", vector_id)
        
        try:
            if not self.vector_search_api_endpoint:
                raise ValueError("vector_search_api_endpoint is required for get operation")

            vector_search_client = aiplatform_v1.MatchServiceClient(
                client_options={
                    "api_endpoint": self.vector_search_api_endpoint
                },
            )
            datapoint = aiplatform_v1.IndexDatapoint(
                datapoint_id=vector_id
            )

            query = aiplatform_v1.FindNeighborsRequest.Query(
                datapoint=datapoint,
                neighbor_count=1
            )
            request = aiplatform_v1.FindNeighborsRequest(
                index_endpoint=f"projects/{self.project_number}/locations/{self.region}/indexEndpoints/{self.endpoint_id}",
                deployed_index_id=self.deployment_index_id,
                queries=[query],
                return_full_datapoint=True,
            )

            try:
                response = vector_search_client.find_neighbors(request)
                logger.debug("Got response")
                
                if response and response.nearest_neighbors:
                    nearest = response.nearest_neighbors[0]
                    if nearest.neighbors:
                        neighbor = nearest.neighbors[0]
                        
                        payload = {}
                        if hasattr(neighbor.datapoint, 'restricts'):
                            for restrict in neighbor.datapoint.restricts:
                                if restrict.allow_list:
                                    payload[restrict.namespace] = restrict.allow_list[0]
                
                        return OutputData(
                            id=neighbor.datapoint.datapoint_id,
                            score=neighbor.distance,
                            payload=payload
                        )
                
                logger.debug("No results found")
                return None
                
            except google.api_core.exceptions.NotFound:
                logger.debug("Datapoint not found")
                return None
            except google.api_core.exceptions.PermissionDenied as e:
                logger.error("Permission denied: %s", str(e))
                return None
            
        except Exception as e:
            logger.error("Error occurred: %s", str(e))
            logger.error("Error type: %s", type(e))
            logger.error("Stack trace: %s", traceback.format_exc())
            raise


    def list_cols(self) -> List[str]:
        """
        List all collections (indexes).
        Returns:
            List[str]: List of collection names.
        """
        return [self.deployment_index_id]


    def delete_col(self):
        """
        Delete a collection (index).
        Note: This operation is not supported through the API.
        """
        logger.warning("Delete collection operation is not supported for Google Matching Engine")
        pass


    def col_info(self) -> Dict:
        """
        Get information about a collection (index).
        Returns:
            Dict: Collection information.
        """
        return {
            "index_id": self.index_id,
            "endpoint_id": self.endpoint_id,
            "project_id": self.project_id,
            "region": self.region
        }


    def list(self, filters: Optional[Dict] = None, limit: Optional[int] = None) -> List[List[OutputData]]:
        """List vectors matching the given filters.
        
        Args:
            filters: Optional filters to apply
            limit: Optional maximum number of results to return
            
        Returns:
            List[List[OutputData]]: List of matching vectors wrapped in an extra array
            to match the interface
        """
        logger.debug("Starting list operation")
        logger.debug("Filters: %s", filters)
        logger.debug("Limit: %s", limit)
        
        try:
            # Use a zero vector for the search
            dimension = 768  # This should be configurable based on the model
            zero_vector = [0.0] * dimension
            
            # Use a large limit if none specified
            search_limit = limit if limit is not None else 10000
            
            results = self.search(
                query=zero_vector,
                limit=search_limit,
                filters=filters
            )
            
            logger.debug("Found %d results", len(results))
            return [results]  # Wrap in extra array to match interface
            
        except Exception as e:
            logger.error("Error in list operation: %s", str(e))
            logger.error("Stack trace: %s", traceback.format_exc())
            raise


    def create_col(self, name=None, vector_size=None, distance=None):
        """
        Create a new collection. For Google Matching Engine, collections (indexes) 
        are created through the Google Cloud Console or API separately.
        This method is a no-op since indexes are pre-created.
        
        Args:
            name: Ignored for Google Matching Engine
            vector_size: Ignored for Google Matching Engine
            distance: Ignored for Google Matching Engine
        """
        # Google Matching Engine indexes are created through Google Cloud Console
        # This method is included only to satisfy the abstract base class
        pass


    def add(self, text: str, metadata: Optional[Dict] = None, user_id: Optional[str] = None) -> str:
        logger.debug("Starting add operation")
        logger.debug("Text: %s", text)
        logger.debug("Metadata: %s", metadata)
        logger.debug("User ID: %s", user_id)
        
        try:
            # Generate a unique ID for this entry
            vector_id = str(uuid.uuid4())
            
            # Create the payload with all necessary fields
            payload = {
                "data": text,  # Store the text in the data field
                "user_id": user_id,
                **(metadata or {})
            }
            
            # Get the embedding
            vector = self.embedder.embed_query(text)
            
            # Insert using the insert method
            self.insert(
                vectors=[vector],
                payloads=[payload],
                ids=[vector_id]
            )
            
            return vector_id
            
        except Exception as e:
            logger.error("Error occurred: %s", str(e))
            raise


    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """Add texts to the vector store.
        
        Args:
            texts: List of texts to add
            metadatas: Optional list of metadata dicts
            ids: Optional list of IDs to use
            
        Returns:
            List[str]: List of IDs of the added texts
            
        Raises:
            ValueError: If texts is empty or lengths don't match
        """
        if not texts:
            raise ValueError("No texts provided")
        
        if metadatas and len(metadatas) != len(texts):
            raise ValueError(f"Number of metadata items ({len(metadatas)}) does not match number of texts ({len(texts)})")
        
        if ids and len(ids) != len(texts):
            raise ValueError(f"Number of ids ({len(ids)}) does not match number of texts ({len(texts)})")
        
        logger.debug("Starting add_texts operation")
        logger.debug("Number of texts: %d", len(texts))
        logger.debug("Has metadatas: %s", metadatas is not None)
        logger.debug("Has ids: %s", ids is not None)
        
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts]
        
        try:
            # Get embeddings
            embeddings = self.embedder.embed_documents(texts)
            
            # Add to store
            self.insert(
                vectors=embeddings,
                payloads=metadatas if metadatas else [{}] * len(texts),
                ids=ids
            )
            return ids
            
        except Exception as e:
            logger.error("Error in add_texts: %s", str(e))
            logger.error("Stack trace: %s", traceback.format_exc())
            raise

    @classmethod
    def from_texts(
        cls,
        texts: List[str],
        embedding: Any,
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> "GoogleMatchingEngine":
        """Create an instance from texts."""
        logger.debug("Creating instance from texts")
        store = cls(**kwargs)
        store.add_texts(texts=texts, metadatas=metadatas, ids=ids)
        return store

    def similarity_search_with_score(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict] = None,
    ) -> List[Tuple[Document, float]]:
        """Return documents most similar to query with scores."""
        logger.debug("Starting similarity search with score")
        logger.debug("Query: %s", query)
        logger.debug("k: %d", k)
        logger.debug("Filter: %s", filter)
        
        embedding = self.embedder.embed_query(query)
        results = self.search(query=embedding, limit=k, filters=filter)
        
        docs_and_scores = [
            (
                Document(
                    page_content=result.payload.get("text", ""),
                    metadata=result.payload
                ),
                result.score
            )
            for result in results
        ]
        logger.debug("Found %d results", len(docs_and_scores))
        return docs_and_scores

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict] = None,
    ) -> List[Document]:
        """Return documents most similar to query."""
        logger.debug("Starting similarity search")
        docs_and_scores = self.similarity_search_with_score(query, k, filter)
        return [doc for doc, _ in docs_and_scores]

