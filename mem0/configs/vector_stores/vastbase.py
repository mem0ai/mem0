from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VastbaseConfig(BaseModel):
    dbname: str = Field("mem0", description="Database name")
    collection_name: str = Field("mem0", description="Collection name")
    embedding_model_dims: Optional[int] = Field(1536, description="Dimensions of the embedding model")
    user: Optional[str] = Field(None, description="Database user")
    password: Optional[str] = Field(None, description="Database password")
    host: Optional[str] = Field("localhost", description="Database host")
    port: Optional[int] = Field(5432, description="Database port")
    m: Optional[int] = Field(16, description="Graph index parameter: max connections per node (2-100)")
    ef_construction: Optional[int] = Field(200, description="Graph index build parameter: candidate list size (4-1000)")
    ef_search: Optional[int] = Field(100, description="Graph index search parameter: search candidate list size")
    quantizer: Optional[str] = Field(None, description="Quantization method: 'pq' or 'rabitq'")
    parallel_workers: Optional[int] = Field(0, description="Parallel workers for index build (0-64)")
    connection_string: Optional[str] = Field(None, description="Connection string (overrides individual params)")

    @model_validator(mode="before")
    def check_auth(cls, values):
        if values.get("connection_string") is not None:
            return values
        user = values.get("user")
        password = values.get("password")
        if not user or not password:
            raise ValueError("Both 'user' and 'password' must be provided when not using connection_string.")
        return values

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. "
                f"Allowed fields: {', '.join(allowed_fields)}"
            )
        return values

    model_config = ConfigDict(arbitrary_types_allowed=True)
