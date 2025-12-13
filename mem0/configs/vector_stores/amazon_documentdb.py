from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class AmazonDocumentDBConfig(BaseModel):
    """Configuration for Amazon DocumentDB vector database."""

    db_name: str = Field("mem0_db", description="Name of the DocumentDB database")
    collection_name: str = Field("mem0", description="Name of the DocumentDB collection")
    embedding_model_dims: Optional[int] = Field(1024, description="Dimensions of the embedding vectors (1024 for Titan, 1536 for other models)")
    mongo_uri: str = Field(
        "mongodb://username:password@docdb-cluster.cluster-xyz.us-west-2.docdb.amazonaws.com:27017/?tls=true&tlsCAFile=global-bundle.pem",
        description="DocumentDB URI with TLS enabled. Example: mongodb://username:password@docdb-cluster.cluster-xyz.us-west-2.docdb.amazonaws.com:27017/?tls=true&tlsCAFile=global-bundle.pem"
    )

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
