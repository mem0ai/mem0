from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


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
    index_name: str = Field("mem0", description="Vector search index name")
    index_type: str = Field("DELTA_SYNC", description="Index type: DELTA_SYNC or DIRECT_ACCESS")
    embedding_model_endpoint_name: Optional[str] = Field(
        None, description="Embedding model endpoint for Databricks-computed embeddings"
    )
    embedding_dimension: int = Field(1536, description="Vector embedding dimensions")
    endpoint_type: str = Field("STANDARD", description="Endpoint type: STANDARD or STORAGE_OPTIMIZED")
    pipeline_type: str = Field("TRIGGERED", description="Sync pipeline type: TRIGGERED or CONTINUOUS")
    warehouse_id: Optional[str] = Field(None, description="Databricks SQL warehouse ID")
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
        has_service_principal = (
            self.service_principal_client_id is not None and self.service_principal_client_secret is not None
        )

        if not has_token and not has_service_principal:
            raise ValueError(
                "Either access_token or both service_principal_client_id and service_principal_client_secret must be provided"
            )

        return self

    @model_validator(mode="after")
    def validate_endpoint_type(self):
        """Validate endpoint type."""
        if self.endpoint_type not in ["STANDARD", "STORAGE_OPTIMIZED"]:
            raise ValueError("endpoint_type must be either 'STANDARD' or 'STORAGE_OPTIMIZED'")
        return self

    @model_validator(mode="after")
    def validate_pipeline_type(self):
        """Validate pipeline type."""
        if self.pipeline_type not in ["TRIGGERED", "CONTINUOUS"]:
            raise ValueError("pipeline_type must be either 'TRIGGERED' or 'CONTINUOUS'")
        return self

    model_config = {
        "arbitrary_types_allowed": True,
    }
