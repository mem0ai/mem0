import logging
import uuid
from typing import Dict, List, Mapping, Optional

from pydantic import BaseModel

try:
    import weaviate
except ImportError:
    raise ImportError(
        "The 'weaviate' library is required. Please install it using 'pip install weaviate-client weaviate'."
    )

import weaviate.classes.config as wvcc
from weaviate.classes.init import Auth
from weaviate.classes.query import Filter, MetadataQuery
from weaviate.util import get_valid_uuid

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: str
    score: float
    payload: Dict


class Weaviate(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        embedding_model_dims: int,
        cluster_url: str = None,
        auth_client_secret: str = None,
        additional_headers: dict = None,
    ):
        """
        Initialize the Weaviate vector store.

        Args:
            collection_name (str): Name of the collection/class in Weaviate.
            embedding_model_dims (int): Dimensions of the embedding model.
            client (WeaviateClient, optional): Existing Weaviate client instance. Defaults to None.
            cluster_url (str, optional): URL for Weaviate server. Defaults to None.
            auth_config (dict, optional): Authentication configuration for Weaviate. Defaults to None.
            additional_headers (dict, optional): Additional headers for requests. Defaults to None.
        """
        if "localhost" in cluster_url:
            self.client = weaviate.connect_to_local(headers=additional_headers)
        else:
            self.client = weaviate.connect_to_wcs(
                cluster_url=cluster_url,
                auth_credentials=Auth.api_key(auth_client_secret),
                headers=additional_headers,
            )

        self.collection_name = collection_name
        self.create_col(embedding_model_dims)

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

    def create_col(self, vector_size, distance="cosine"):
        """
        Create a new collection with the specified schema.

        Args:
            vector_size (int): Size of the vectors to be stored.
            distance (str, optional): Distance metric for vector similarity. Defaults to "cosine".
        """
        if self.client.collections.exists(self.collection_name):
            logging.debug(f"Collection {self.collection_name} already exists. Skipping creation.")
            return

        properties = [
            wvcc.Property(name="ids", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="hash", data_type=wvcc.DataType.TEXT),
            wvcc.Property(
                name="metadata",
                data_type=wvcc.DataType.TEXT,
                description="Additional metadata",
            ),
            wvcc.Property(name="data", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="created_at", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="category", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="updated_at", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="user_id", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="agent_id", data_type=wvcc.DataType.TEXT),
            wvcc.Property(name="run_id", data_type=wvcc.DataType.TEXT),
        ]

        vectorizer_config = wvcc.Configure.Vectorizer.none()
        vector_index_config = wvcc.Configure.VectorIndex.hnsw()

        self.client.collections.create(
            self.collection_name,
            vectorizer_config=vectorizer_config,
            vector_index_config=vector_index_config,
            properties=properties,
        )

    def insert(self, vectors, payloads=None, ids=None):
        """
        Insert vectors into a collection.

        Args:
            vectors (list): List of vectors to insert.
            payloads (list, optional): List of payloads corresponding to vectors. Defaults to None.
            ids (list, optional): List of IDs corresponding to vectors. Defaults to None.
        """
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")
        with self.client.batch.fixed_size(batch_size=100) as batch:
            for idx, vector in enumerate(vectors):
                object_id = ids[idx] if ids and idx < len(ids) else str(uuid.uuid4())
                object_id = get_valid_uuid(object_id)

                data_object = payloads[idx] if payloads and idx < len(payloads) else {}

                # Ensure 'id' is not included in properties (it's used as the Weaviate object ID)
                if "ids" in data_object:
                    del data_object["ids"]

                batch.add_object(collection=self.collection_name, properties=data_object, uuid=object_id, vector=vector)

    def search(
        self, query: str, vectors: List[float], limit: int = 5, filters: Optional[Dict] = None
    ) -> List[OutputData]:
        """
        Search for similar vectors.
        """
        collection = self.client.collections.get(str(self.collection_name))
        filter_conditions = []
        if filters:
            for key, value in filters.items():
                if value and key in ["user_id", "agent_id", "run_id"]:
                    filter_conditions.append(Filter.by_property(key).equal(value))
        combined_filter = Filter.all_of(filter_conditions) if filter_conditions else None
        response = collection.query.hybrid(
            query="",
            vector=vectors,
            limit=limit,
            filters=combined_filter,
            return_properties=["hash", "created_at", "updated_at", "user_id", "agent_id", "run_id", "data", "category"],
            return_metadata=MetadataQuery(score=True),
        )
        results = []
        for obj in response.objects:
            payload = obj.properties.copy()

            for id_field in ["run_id", "agent_id", "user_id"]:
                if id_field in payload and payload[id_field] is None:
                    del payload[id_field]

            payload["id"] = str(obj.uuid).split("'")[0]  # Include the id in the payload
            results.append(
                OutputData(
                    id=str(obj.uuid),
                    score=1
                    if obj.metadata.distance is None
                    else 1 - obj.metadata.distance,  # Convert distance to score
                    payload=payload,
                )
            )
        return results

    def delete(self, vector_id):
        """
        Delete a vector by ID.

        Args:
            vector_id: ID of the vector to delete.
        """
        collection = self.client.collections.get(str(self.collection_name))
        collection.data.delete_by_id(vector_id)

    def update(self, vector_id, vector=None, payload=None):
        """
        Update a vector and its payload.

        Args:
            vector_id: ID of the vector to update.
            vector (list, optional): Updated vector. Defaults to None.
            payload (dict, optional): Updated payload. Defaults to None.
        """
        collection = self.client.collections.get(str(self.collection_name))

        if payload:
            collection.data.update(uuid=vector_id, properties=payload)

        if vector:
            existing_data = self.get(vector_id)
            if existing_data:
                existing_data = dict(existing_data)
                if "id" in existing_data:
                    del existing_data["id"]
                existing_payload: Mapping[str, str] = existing_data
                collection.data.update(uuid=vector_id, properties=existing_payload, vector=vector)

    def get(self, vector_id):
        """
        Retrieve a vector by ID.

        Args:
            vector_id: ID of the vector to retrieve.

        Returns:
            dict: Retrieved vector and metadata.
        """
        vector_id = get_valid_uuid(vector_id)
        collection = self.client.collections.get(str(self.collection_name))

        response = collection.query.fetch_object_by_id(
            uuid=vector_id,
            return_properties=["hash", "created_at", "updated_at", "user_id", "agent_id", "run_id", "data", "category"],
        )
        # results = {}
        # print("reponse",response)
        # for obj in response.objects:
        payload = response.properties.copy()
        payload["id"] = str(response.uuid).split("'")[0]
        results = OutputData(
            id=str(response.uuid).split("'")[0],
            score=1.0,
            payload=payload,
        )
        return results

    def list_cols(self):
        """
        List all collections.

        Returns:
            list: List of collection names.
        """
        collections = self.client.collections.list_all()
        logger.debug(f"collections: {collections}")
        print(f"collections: {collections}")
        return {"collections": [{"name": col.name} for col in collections]}

    def delete_col(self):
        """Delete a collection."""
        self.client.collections.delete(self.collection_name)

    def col_info(self):
        """
        Get information about a collection.

        Returns:
            dict: Collection information.
        """
        schema = self.client.collections.get(self.collection_name)
        if schema:
            return schema
        return None

    def list(self, filters=None, limit=100) -> List[OutputData]:
        """
        List all vectors in a collection.
        """
        collection = self.client.collections.get(self.collection_name)
        filter_conditions = []
        if filters:
            for key, value in filters.items():
                if value and key in ["user_id", "agent_id", "run_id"]:
                    filter_conditions.append(Filter.by_property(key).equal(value))
        combined_filter = Filter.all_of(filter_conditions) if filter_conditions else None
        response = collection.query.fetch_objects(
            limit=limit,
            filters=combined_filter,
            return_properties=["hash", "created_at", "updated_at", "user_id", "agent_id", "run_id", "data", "category"],
        )
        results = []
        for obj in response.objects:
            payload = obj.properties.copy()
            payload["id"] = str(obj.uuid).split("'")[0]
            results.append(OutputData(id=str(obj.uuid).split("'")[0], score=1.0, payload=payload))
        return [results]
