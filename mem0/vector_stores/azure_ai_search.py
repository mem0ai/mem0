import json
import logging
from typing import List, Optional

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

try:
    from azure.core.credentials import AzureKeyCredential
    from azure.core.exceptions import ResourceNotFoundError
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration,
        ScalarQuantizationCompression,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        SimpleField,
        VectorSearch,
        VectorSearchProfile,
    )
    from azure.search.documents.models import VectorizedQuery
except ImportError:
    raise ImportError(
        "The 'azure-search-documents' library is required. Please install it using 'pip install azure-search-documents==11.5.1'."
    )

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class AzureAISearch(VectorStoreBase):
    def __init__(self, service_name, collection_name, api_key, embedding_model_dims, use_compression):
        """Initialize the Azure Cognitive Search vector store.

        Args:
            service_name (str): Azure Cognitive Search service name.
            collection_name (str): Index name.
            api_key (str): API key for the Azure Cognitive Search service.
            embedding_model_dims (int): Dimension of the embedding vector.
            use_compression (bool): Use scalar quantization vector compression
        """
        self.index_name = collection_name
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.use_compression = use_compression
        self.search_client = SearchClient(
            endpoint=f"https://{service_name}.search.windows.net",
            index_name=self.index_name,
            credential=AzureKeyCredential(api_key),
        )
        self.index_client = SearchIndexClient(
            endpoint=f"https://{service_name}.search.windows.net", credential=AzureKeyCredential(api_key)
        )
        self.create_col()  # create the collection / index

    def create_col(self):
        """Create a new index in Azure Cognitive Search."""
        vector_dimensions = self.embedding_model_dims  # Set this to the number of dimensions in your vector

        if self.use_compression:
            vector_type = "Collection(Edm.Half)"
            compression_name = "myCompression"
            compression_configurations = [ScalarQuantizationCompression(compression_name=compression_name)]
        else:
            vector_type = "Collection(Edm.Single)"
            compression_name = None
            compression_configurations = []

        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchField(
                name="vector",
                type=vector_type,
                searchable=True,
                vector_search_dimensions=vector_dimensions,
                vector_search_profile_name="my-vector-config",
            ),
            SimpleField(name="payload", type=SearchFieldDataType.String, searchable=True),
        ]

        vector_search = VectorSearch(
            profiles=[
                VectorSearchProfile(name="my-vector-config", algorithm_configuration_name="my-algorithms-config")
            ],
            algorithms=[HnswAlgorithmConfiguration(name="my-algorithms-config")],
            compressions=compression_configurations,
        )
        index = SearchIndex(name=self.index_name, fields=fields, vector_search=vector_search)
        self.index_client.create_or_update_index(index)

    def insert(self, vectors, payloads=None, ids=None):
        """Insert vectors into the index.

        Args:
            vectors (List[List[float]]): List of vectors to insert.
            payloads (List[Dict], optional): List of payloads corresponding to vectors.
            ids (List[str], optional): List of IDs corresponding to vectors.
        """
        logger.info(f"Inserting {len(vectors)} vectors into index {self.index_name}")
        documents = [
            {"id": id, "vector": vector, "payload": json.dumps(payload)}
            for id, vector, payload in zip(ids, vectors, payloads)
        ]
        self.search_client.upload_documents(documents)

    def search(self, query, limit=5, filters=None):
        """Search for similar vectors.

        Args:
            query (List[float]): Query vectors.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """

        vector_query = VectorizedQuery(vector=query, k_nearest_neighbors=limit, fields="vector")
        search_results = self.search_client.search(vector_queries=[vector_query], top=limit)

        results = []
        for result in search_results:
            payload = json.loads(result["payload"])
            if filters:
                for key, value in filters.items():
                    if key not in payload or payload[key] != value:
                        continue
            results.append(OutputData(id=result["id"], score=result["@search.score"], payload=payload))
        return results

    def delete(self, vector_id):
        """Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        self.search_client.delete_documents(documents=[{"id": vector_id}])

    def update(self, vector_id, vector=None, payload=None):
        """Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (List[float], optional): Updated vector.
            payload (Dict, optional): Updated payload.
        """
        document = {"id": vector_id}
        if vector:
            document["vector"] = vector
        if payload:
            document["payload"] = json.dumps(payload)
        self.search_client.merge_or_upload_documents(documents=[document])

    def get(self, vector_id) -> OutputData:
        """Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector.
        """
        try:
            result = self.search_client.get_document(key=vector_id)
        except ResourceNotFoundError:
            return None
        return OutputData(id=result["id"], score=None, payload=json.loads(result["payload"]))

    def list_cols(self) -> List[str]:
        """List all collections (indexes).

        Returns:
            List[str]: List of index names.
        """
        indexes = self.index_client.list_indexes()
        return [index.name for index in indexes]

    def delete_col(self):
        """Delete the index."""
        self.index_client.delete_index(self.index_name)

    def col_info(self):
        """Get information about the index.

        Returns:
            Dict[str, Any]: Index information.
        """
        index = self.index_client.get_index(self.index_name)
        return {"name": index.name, "fields": index.fields}

    def list(self, filters=None, limit=100):
        """List all vectors in the index.

        Args:
            filters (Dict, optional): Filters to apply to the list.
            limit (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            List[OutputData]: List of vectors.
        """
        search_results = self.search_client.search(search_text="*", top=limit)
        results = []
        for result in search_results:
            payload = json.loads(result["payload"])
            include_result = True
            if filters:
                for key, value in filters.items():
                    if (key not in payload) or (payload[key] != filters[key]):
                        include_result = False
                        break
            if include_result:
                results.append(OutputData(id=result["id"], score=result["@search.score"], payload=payload))

        return [results]

    def __del__(self):
        """Close the search client when the object is deleted."""
        self.search_client.close()
        self.index_client.close()
