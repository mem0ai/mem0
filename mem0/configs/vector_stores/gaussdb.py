import os
import re
from typing import Any, Dict, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


_ENV_DEFAULTS = {
    "connection_string": ("GAUSSDB_CONNECTION_STRING", "GAUSSDB_DSN", "GAUSSDB_URL"),
    "host": ("GAUSSDB_HOST",),
    "port": ("GAUSSDB_PORT",),
    "database": ("GAUSSDB_DATABASE", "GAUSSDB_DBNAME"),
    "user": ("GAUSSDB_USER",),
    "password": ("GAUSSDB_PASSWORD",),
    "sslmode": ("GAUSSDB_SSLMODE",),
    "sslrootcert": ("GAUSSDB_SSLROOTCERT",),
    "schema": ("GAUSSDB_SCHEMA",),
}

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def _first_env(names: tuple[str, ...]) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


class GaussDBConfig(BaseModel):
    # Connection
    database: str = Field("postgres", description="GaussDB database name")
    collection_name: str = Field("mem0", description="Name of the collection table")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    user: Optional[str] = Field(None, description="Database user")
    password: Optional[str] = Field(None, description="Database password")
    host: Optional[str] = Field(None, description="Database host")
    port: Optional[int] = Field(None, description="Database port")
    connection_string: Optional[str] = Field(None, description="GaussDB connection string (overrides host/port/user/password)")
    sslmode: Optional[str] = Field(None, description="SSL mode (e.g., require, prefer, disable)")
    sslrootcert: Optional[str] = Field(None, description="SSL root certificate path")
    schema_name: str = Field(
        "public",
        validation_alias=AliasChoices("schema", "schema_name"),
        serialization_alias="schema",
        description="Optional advanced schema name; defaults to public",
    )
    minconn: int = Field(1, description="Minimum number of connections in the pool")
    maxconn: int = Field(5, description="Maximum number of connections in the pool")

    # Deployment & Vector
    deployment_mode: str = Field(
        "centralized",
        description="GaussDB deployment mode: centralized or distributed",
    )
    vector_index_type: str = Field("gsdiskann", description="Vector index type: gsdiskann or gsivfflat")
    vector_metric: str = Field("cosine", description="Vector metric: cosine or l2")

    # Operational
    auto_create: bool = Field(True, description="Automatically create collection on init if it does not exist")
    require_scoped_filters: bool = Field(
        False,
        description="Optionally require at least one positive scoped filter (user_id, agent_id, run_id) on read paths; recommended for production multi-tenant use",
    )
    metadata_schema: Dict[str, str] = Field(
        default_factory=dict,
        description="Optional advanced metadata type declarations used for typed range and future typed filter behavior",
    )

    @model_validator(mode="before")
    @classmethod
    def resolve_env_and_validate(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        for field, env_names in _ENV_DEFAULTS.items():
            if not values.get(field):
                env_val = _first_env(env_names)
                if env_val:
                    values[field] = env_val

        allowed_fields = set(cls.model_fields.keys()) | {"schema"}
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. "
                f"Allowed fields: {', '.join(sorted(allowed_fields))}"
            )

        if not values.get("connection_string"):
            user, password = values.get("user"), values.get("password")
            host, port = values.get("host"), values.get("port")
            if bool(user) != bool(password):
                raise ValueError("When 'connection_string' is not provided, both 'user' and 'password' must be provided together.")
            if not user and not password:
                raise ValueError("Either 'connection_string' or both 'user' and 'password' must be provided.")
            if bool(host) != bool(port):
                raise ValueError("When 'connection_string' is not provided, both 'host' and 'port' must be provided together.")
            if not host and not port:
                raise ValueError("Either 'connection_string' or both 'host' and 'port' must be provided.")
        return values

    @model_validator(mode="after")
    def validate_values(self):
        if self.deployment_mode not in ("centralized", "distributed"):
            raise ValueError(f"deployment_mode must be 'centralized' or 'distributed', got '{self.deployment_mode}'")
        if self.vector_index_type not in ("gsdiskann", "gsivfflat"):
            raise ValueError(f"vector_index_type must be 'gsdiskann' or 'gsivfflat', got '{self.vector_index_type}'")
        if self.vector_metric not in ("cosine", "l2"):
            raise ValueError(f"vector_metric must be 'cosine' or 'l2', got '{self.vector_metric}'")
        if self.deployment_mode == "distributed" and self.embedding_model_dims > 1024:
            raise ValueError(
                f"GaussDB distributed mode only supports embedding dimensions <= 1024, "
                f"but embedding_model_dims={self.embedding_model_dims}."
            )
        if self.deployment_mode == "centralized" and self.embedding_model_dims > 4096:
            raise ValueError(
                f"GaussDB centralized mode only supports embedding dimensions <= 4096, "
                f"but embedding_model_dims={self.embedding_model_dims}."
            )
        if self.embedding_model_dims > 1024 and self.vector_index_type != "gsdiskann":
            raise ValueError(
                f"embedding_model_dims={self.embedding_model_dims} exceeds 1024; "
                f"only GsDiskANN supports >1024 dimensions. Set vector_index_type='gsdiskann'."
            )
        if self.minconn < 1:
            raise ValueError("minconn must be >= 1")
        if self.maxconn < 1:
            raise ValueError("maxconn must be >= 1")
        if self.maxconn < self.minconn:
            raise ValueError("maxconn must be >= minconn")
        if not isinstance(self.schema_name, str) or not _IDENTIFIER_RE.match(self.schema_name):
            raise ValueError("schema must be a safe identifier using letters, numbers, and underscores")
        allowed_metadata_types = {"string", "text", "number", "bool", "datetime"}
        for key, value in self.metadata_schema.items():
            if not isinstance(key, str) or not key:
                raise ValueError("metadata_schema keys must be non-empty strings")
            if value not in allowed_metadata_types:
                raise ValueError(
                    f"metadata_schema[{key!r}] must be one of {sorted(allowed_metadata_types)}, got {value!r}"
                )
        return self

    @property
    def schema(self) -> str:
        return self.schema_name

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)
