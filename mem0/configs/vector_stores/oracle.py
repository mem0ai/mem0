from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OracleIndexConfig(BaseModel):
    """Configuration for an Oracle AI Vector Search index."""

    create: bool = Field(True, description="Whether to create a vector index automatically")
    type: Literal["hnsw", "ivf"] = Field("hnsw", description="Oracle vector index type")
    target_accuracy: Optional[int] = Field(None, ge=1, le=100, description="Target accuracy for index creation")
    neighbors: int = Field(40, ge=2, le=2048, description="HNSW neighbors parameter")
    efconstruction: int = Field(500, ge=1, le=65535, description="HNSW EFCONSTRUCTION parameter")
    neighbor_partitions: int = Field(100, ge=1, le=10000000, description="IVF neighbor partitions")
    parallel: Optional[int] = Field(None, ge=1, description="Parallel degree for vector index creation")

    @model_validator(mode="before")
    @classmethod
    def normalize_index_type(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if values is None:
            return {}
        if "type" in values and isinstance(values["type"], str):
            values["type"] = values["type"].lower()
        return values

    model_config = ConfigDict(extra="forbid")


class OracleConfig(BaseModel):
    """Configuration for Oracle AI Database as a Mem0 vector store."""

    dsn: Optional[str] = Field(None, description="Oracle Database DSN, for example localhost:1521/FREEPDB1")
    user: Optional[str] = Field(None, description="Oracle Database user")
    password: Optional[str] = Field(None, description="Oracle Database password")
    collection_name: str = Field("mem0", description="Oracle table name for storing Mem0 vectors")
    embedding_model_dims: int = Field(1536, gt=0, description="Dimensions of the embedding model")
    vector_format: Literal["FLOAT32", "FLOAT64"] = Field("FLOAT32", description="Oracle VECTOR storage format")
    distance: str = Field("COSINE", description="Oracle VECTOR_DISTANCE metric")
    search_mode: Literal["approx", "exact", "auto"] = Field("approx", description="Vector search mode")
    target_accuracy: int = Field(90, ge=1, le=100, description="Query-time target accuracy for approximate search")
    auto_create: bool = Field(True, description="Whether to create the table and indexes automatically")
    index: Optional[OracleIndexConfig] = Field(default_factory=OracleIndexConfig, description="Vector index settings")
    minconn: int = Field(1, ge=1, description="Minimum number of connections in the pool")
    maxconn: int = Field(5, ge=1, description="Maximum number of connections in the pool")
    increment: int = Field(1, ge=1, description="Connection pool increment")
    connection_pool: Optional[Any] = Field(None, description="Existing oracledb connection pool")
    config_dir: Optional[str] = Field(None, description="Oracle Net configuration directory")
    wallet_location: Optional[str] = Field(None, description="Oracle wallet location")
    wallet_password: Optional[str] = Field(None, description="Oracle wallet password")
    thick_mode: bool = Field(False, description="Initialize python-oracledb in thick mode")
    lib_dir: Optional[str] = Field(None, description="Oracle Client library directory for thick mode")
    pool_kwargs: Dict[str, Any] = Field(default_factory=dict, description="Additional oracledb.create_pool kwargs")

    @model_validator(mode="before")
    @classmethod
    def normalize_and_validate(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if values is None:
            values = {}

        if "distance" in values and isinstance(values["distance"], str):
            values["distance"] = values["distance"].upper()

        if "vector_format" in values and isinstance(values["vector_format"], str):
            values["vector_format"] = values["vector_format"].upper()

        if "search_mode" in values and isinstance(values["search_mode"], str):
            values["search_mode"] = values["search_mode"].lower()

        if values.get("connection_pool") is not None:
            return values

        if not values.get("dsn"):
            raise ValueError("'dsn' must be provided when not using connection_pool.")

        if not values.get("user") or not values.get("password"):
            raise ValueError("Both 'user' and 'password' must be provided when not using connection_pool.")

        return values

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")
