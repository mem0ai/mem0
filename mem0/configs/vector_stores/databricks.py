from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from databricks.sdk.service.vectorsearch import EndpointType, VectorIndexType, PipelineType


class DatabricksConfig(BaseModel):
    """Configuration for Databricks Vector Search vector store."""

    workspace_url: str = Field(..., description="Databricks workspace URL")
    access_token: Optional[str] = Field(None, description="Personal access token for authentication")
    client_id: Optional[str] = Field(None, description="Databricks Service principal client ID")
    client_secret: Optional[str] = Field(None, description="Databricks Service principal client secret")
    azure_client_id: Optional[str] = Field(None, description="Azure AD application client ID (for Azure Databricks)")
    azure_client_secret: Optional[str] = Field(
        None, description="Azure AD application client secret (for Azure Databricks)"
    )
    endpoint_name: str = Field(..., description="Vector search endpoint name")
    catalog: str = Field(..., description="The Unity Catalog catalog name")
    schema: str = Field(..., description="The Unity Catalog schama name")
    table_name: str = Field(..., description="Source Delta table name")
    collection_name: str = Field("mem0", description="Vector search index name")
    index_type: VectorIndexType = Field("DELTA_SYNC", description="Index type: DELTA_SYNC or DIRECT_ACCESS")
    embedding_model_endpoint_name: Optional[str] = Field(
        None, description="Embedding model endpoint for Databricks-computed embeddings"
    )
    embedding_dimension: int = Field(1536, description="Vector embedding dimensions")
    endpoint_type: EndpointType = Field("STANDARD", description="Endpoint type: STANDARD or STORAGE_OPTIMIZED")
    pipeline_type: PipelineType = Field("TRIGGERED", description="Sync pipeline type: TRIGGERED or CONTINUOUS")
    warehouse_name: Optional[str] = Field(None, description="Databricks SQL warehouse Name")
    query_type: str = Field("ANN", description="Query type: `ANN` and `HYBRID`")

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

    @model_validator(mode="after")
    def validate_authentication(self):
        """Validate that either access_token or service principal credentials are provided."""
        has_token = self.access_token is not None
        has_service_principal = (self.client_id is not None and self.client_secret is not None) or (
            self.azure_client_id is not None and self.azure_client_secret is not None
        )

        if not has_token and not has_service_principal:
            raise ValueError(
                "Either access_token or both client_id/client_secret or azure_client_id/azure_client_secret must be provided"
            )

        return self

    model_config = ConfigDict(arbitrary_types_allowed=True)
