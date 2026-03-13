from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

class AzureCosmosDBConfig(BaseModel):
    """Configuration for Cosmos DB vector database."""

    # Required fields — no default, must be supplied by the caller
    cosmos_client: Any = Field(..., description="CosmosClient used to connect to azure cosmosdb no sql account")
    vector_properties: Dict[str, Any] = Field(..., description="Vector embedding properties for the collection. Must contain 'path', 'dataType', 'dimensions', and 'distanceFunction'")
    vector_search_fields: Dict[str, Any] = Field(..., description="Field name mapping for search. Must contain 'text_field' and 'vector_field'")

    # Optional fields — safe to omit, sensible defaults apply
    indexing_policy: Optional[Dict[str, Any]] = Field(None, description="Indexing policy for the collection. Must include 'fullTextIndexes' when full_text_search_enabled=True")
    cosmos_database_properties: Optional[Dict[str, Any]] = Field(None, description="Extra properties forwarded to create_database_if_not_exists (e.g. offer_throughput, etag)")
    cosmos_collection_properties: Optional[Dict[str, Any]] = Field(None, description="Container properties forwarded to create_container_if_not_exists. Must include 'partition_key' when create_collection=True")
    database_name: str = Field("vectorSearchDB", description="Name of the database to be created")
    collection_name: str = Field("vectorSearchContainer", description="Name of the collection to be created")
    search_type: str = Field("vector", description="CosmosDB search type to be performed")
    metadata_key: str = Field("metadata", description="Metadata key to use for data schema")
    create_collection: bool = Field(True, description="Set to true if the collection does not exist")
    table_alias: str = Field("c", description="Alias for the table to use in the WHERE clause")
    full_text_policy: Optional[Dict[str, Any]] = Field(None, description="Full-text policy for the collection. Must include 'fullTextPaths' when full_text_search_enabled=True")
    full_text_search_enabled: bool = Field(False, description="Set to true if full text search is enabled")

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
