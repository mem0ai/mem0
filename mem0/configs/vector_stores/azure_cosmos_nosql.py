import os
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AzureCosmosNoSQLConfig(BaseModel):
    """Configuration for Azure Cosmos DB for NoSQL vector database."""

    collection_name: str = Field("mem0", description="Name of the container")
    database_name: str = Field("mem0db", description="Name of the database")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    client: Optional[Any] = Field(None, description="Existing `azure.cosmos.CosmosClient` instance")
    endpoint: Optional[str] = Field(None, description="Azure Cosmos DB account endpoint URL")
    api_key: Optional[str] = Field(None, description="Azure Cosmos DB account key")
    connection_string: Optional[str] = Field(None, description="Azure Cosmos DB connection string")
    metric: str = Field("cosine", description="Distance function: 'cosine', 'dotproduct' or 'euclidean'")
    index_type: str = Field("diskANN", description="Vector index type: 'flat', 'quantizedFlat' or 'diskANN'")

    @model_validator(mode="before")
    @classmethod
    def check_credentials(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        client = values.get("client")
        connection_string = values.get("connection_string") or os.environ.get("AZURE_COSMOS_CONNECTION_STRING")
        endpoint = values.get("endpoint") or os.environ.get("AZURE_COSMOS_ENDPOINT")
        api_key = values.get("api_key") or os.environ.get("AZURE_COSMOS_KEY")
        if not client and not connection_string and not (endpoint and api_key):
            raise ValueError(
                "Provide one of: 'client', 'connection_string', or 'endpoint' + 'api_key' "
                "(or set AZURE_COSMOS_CONNECTION_STRING, or AZURE_COSMOS_ENDPOINT + AZURE_COSMOS_KEY)."
            )
        return values

    @model_validator(mode="before")
    @classmethod
    def check_metric_and_index_type(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        metric = values.get("metric", "cosine")
        if metric not in ("cosine", "dotproduct", "euclidean"):
            raise ValueError(f"Invalid metric '{metric}'. Must be one of: 'cosine', 'dotproduct', 'euclidean'.")
        index_type = values.get("index_type", "diskANN")
        if index_type not in ("flat", "quantizedFlat", "diskANN"):
            raise ValueError(f"Invalid index_type '{index_type}'. Must be one of: 'flat', 'quantizedFlat', 'diskANN'.")
        return values

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. Please input only the following fields: {', '.join(allowed_fields)}"
            )
        return values

    model_config = ConfigDict(arbitrary_types_allowed=True)
