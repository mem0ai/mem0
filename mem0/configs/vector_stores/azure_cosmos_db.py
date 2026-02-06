from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

class AzureCosmosDBConfig(BaseModel):
    """Configuration for Cosmos DB vector database."""

    cosmos_client: Any = Field(None, description="CosmosClient used to connect to azure cosmosdb no sql account")
    indexing_policy: Dict[str, Any] = Field(None, description="Indexing Policy for the collection")
    cosmos_database_properties: Dict[str, Any] = Field(None, description="Database Properties for the collection")
    cosmos_collection_properties: Dict[str, Any] = Field(None, description="Container Properties for the collection")
    vector_properties: Dict[str, Any] = Field(None, description="Vector Embedding Properties for the collection.")
    vector_search_fields: Dict[str, Any] = Field(None, description="Vector Search and Text Search Fields for the collection")
    database_name: str = Field("vectorSearchDB", description="Name of the database to be created")
    collection_name: str = Field("vectorSearchContainer", description="Name of the collection to be created")
    search_type: str = Field("vector", description="CosmosDB Search Type to be performed")
    metadata_key: str = Field("metadata", description="Metadata key to use for data schema")
    create_collection: bool = Field(True, description="Set to true if the collection does not exist")
    table_alias: str = Field("c", description="Alias for the table to use in the WHERE clause")
    full_text_policy: Optional[Dict[str, Any]] = Field(None, description="Full Text Policy for the collection")
    full_text_search_enabled: bool = Field(False, description="Set to true if the full text search is enabled")

    def __init__(self, **data):
        try:
            from azure.cosmos import CosmosClient
        except ImportError as e:
            raise ImportError(
                "The 'azure-cosmos' library is required. Install it with: pip install azure-cosmos"
            ) from e
        super().__init__(**data)

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. "
                f"Please provide only the following fields: {', '.join(allowed_fields)}."
            )
        return values

    model_config = ConfigDict(arbitrary_types_allowed=True)
