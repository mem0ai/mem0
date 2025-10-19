from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class AzureMySQLConfig(BaseModel):
    """Configuration for Azure MySQL vector database."""

    host: str = Field(..., description="MySQL server host (e.g., myserver.mysql.database.azure.com)")
    port: int = Field(3306, description="MySQL server port")
    user: str = Field(..., description="Database user")
    password: Optional[str] = Field(None, description="Database password (not required if using Azure credential)")
    database: str = Field(..., description="Database name")
    collection_name: str = Field("mem0", description="Collection/table name")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    use_azure_credential: bool = Field(
        False,
        description="Use Azure DefaultAzureCredential for authentication instead of password"
    )
    ssl_ca: Optional[str] = Field(None, description="Path to SSL CA certificate")
    ssl_disabled: bool = Field(False, description="Disable SSL connection (not recommended for production)")
    minconn: int = Field(1, description="Minimum number of connections in the pool")
    maxconn: int = Field(5, description="Maximum number of connections in the pool")
    connection_pool: Optional[Any] = Field(
        None,
        description="Pre-configured connection pool object (overrides other connection parameters)"
    )

    @model_validator(mode="before")
    @classmethod
    def check_auth(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate authentication parameters."""
        # If connection_pool is provided, skip validation
        if values.get("connection_pool") is not None:
            return values

        use_azure_credential = values.get("use_azure_credential", False)
        password = values.get("password")

        # Either password or Azure credential must be provided
        if not use_azure_credential and not password:
            raise ValueError(
                "Either 'password' must be provided or 'use_azure_credential' must be set to True"
            )

        return values

    @model_validator(mode="before")
    @classmethod
    def check_required_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate required fields."""
        # If connection_pool is provided, skip validation of individual parameters
        if values.get("connection_pool") is not None:
            return values

        required_fields = ["host", "user", "database"]
        missing_fields = [field for field in required_fields if not values.get(field)]

        if missing_fields:
            raise ValueError(
                f"Missing required fields: {', '.join(missing_fields)}. "
                f"These fields are required when not using a pre-configured connection_pool."
            )

        return values

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that no extra fields are provided."""
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields

        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. "
                f"Please input only the following fields: {', '.join(allowed_fields)}"
            )

        return values

    class Config:
        arbitrary_types_allowed = True
