from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SingleStoreConfig(BaseModel):
    host: Optional[str] = Field(None, description="SingleStore host")
    port: Optional[int] = Field(3306, description="SingleStore port")
    user: Optional[str] = Field(None, description="Database user")
    password: Optional[str] = Field(None, description="Database password")
    database: Optional[str] = Field(None, description="Database name")
    collection_name: str = Field("mem0", description="Default name for the collection (table)")
    embedding_model_dims: Optional[int] = Field(1536, description="Dimensions of the embedding model")
    connection_url: Optional[str] = Field(None, description="SingleStore connection URL (overrides individual connection parameters)")
    pool_size: Optional[int] = Field(5, description="Connection pool size")
    use_vector_index: Optional[bool] = Field(True, description="Create ANN vector index for faster search")
    use_fulltext_index: Optional[bool] = Field(True, description="Create FULLTEXT index for BM25 keyword search")
    distance_strategy: Optional[str] = Field("DOT_PRODUCT", description="Distance strategy: DOT_PRODUCT or EUCLIDEAN_DISTANCE")

    @model_validator(mode="before")
    @classmethod
    def check_connection(cls, values):
        if values.get("connection_url") is not None:
            return values
        host = values.get("host")
        user = values.get("user")
        password = values.get("password")
        database = values.get("database")
        if not all([host, user, password, database]):
            raise ValueError(
                "Must provide 'host', 'user', 'password', and 'database' when not using 'connection_url'."
            )
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
