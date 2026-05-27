import os
import re
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


_ENV_DEFAULTS = {
    "connection_string": ("GAUSSDB_CONNECTION_STRING", "GAUSSDB_DSN", "GAUSSDB_URL"),
    "host": ("GAUSSDB_HOST",),
    "port": ("GAUSSDB_PORT",),
    "database": ("GAUSSDB_DATABASE", "GAUSSDB_DBNAME"),
    "user": ("GAUSSDB_USER",),
    "password": ("GAUSSDB_PASSWORD",),
    "sslmode": ("GAUSSDB_SSLMODE",),
    "sslrootcert": ("GAUSSDB_SSLROOTCERT",),
    "schema_name": ("GAUSSDB_SCHEMA_NAME", "GAUSSDB_SCHEMA"),
}

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
_MEMORY_SETTING_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([A-Za-z]+)\s*$")
_DEPLOYMENT_MODES = {"centralized", "distributed"}
_VECTOR_INDEX_TYPES = {"gsdiskann", "gsivfflat"}
_VECTOR_METRICS = {"cosine", "l2"}
_MEMORY_UNITS = {"kb", "mb", "gb", "tb"}


def _first_env(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _validate_positive_int(value: int, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be >= 1")
    if value <= 0:
        raise ValueError(f"{field_name} must be >= 1")
    return value


def _normalize_memory_setting(value: Optional[str], field_name: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a memory string like '256MB' or '2GB'")
    match = _MEMORY_SETTING_RE.match(value)
    if not match:
        raise ValueError(f"{field_name} must be a memory string like '256MB' or '2GB'")
    amount, unit = match.groups()
    if unit.lower() not in _MEMORY_UNITS:
        raise ValueError(
            f"{field_name} unit must be one of {sorted(unit.upper() for unit in _MEMORY_UNITS)}, got {unit!r}"
        )
    return f"{amount}{unit.upper()}"


def validate_gaussdb_static_options(
    *,
    embedding_model_dims: int,
    insert_batch_size: int,
    minconn: int,
    maxconn: int,
    schema_name: str,
    deployment_mode: str,
    vector_index_type: str,
    vector_metric: str,
) -> None:
    embedding_model_dims = _validate_positive_int(embedding_model_dims, "embedding_model_dims")
    insert_batch_size = _validate_positive_int(insert_batch_size, "insert_batch_size")
    minconn = _validate_positive_int(minconn, "minconn")
    maxconn = _validate_positive_int(maxconn, "maxconn")

    if deployment_mode not in _DEPLOYMENT_MODES:
        raise ValueError(f"deployment_mode must be 'centralized' or 'distributed', got '{deployment_mode}'")
    if vector_index_type not in _VECTOR_INDEX_TYPES:
        raise ValueError(f"vector_index_type must be 'gsdiskann' or 'gsivfflat', got '{vector_index_type}'")
    if vector_metric not in _VECTOR_METRICS:
        raise ValueError(f"vector_metric must be 'cosine' or 'l2', got '{vector_metric}'")
    if deployment_mode == "distributed" and embedding_model_dims > 1024:
        raise ValueError(
            f"GaussDB distributed mode only supports embedding dimensions <= 1024, "
            f"but embedding_model_dims={embedding_model_dims}."
        )
    if deployment_mode == "centralized" and embedding_model_dims > 4096:
        raise ValueError(
            f"GaussDB centralized mode only supports embedding dimensions <= 4096, "
            f"but embedding_model_dims={embedding_model_dims}."
        )
    if embedding_model_dims > 1024 and vector_index_type != "gsdiskann":
        raise ValueError(
            f"embedding_model_dims={embedding_model_dims} exceeds 1024; "
            f"only GsDiskANN supports >1024 dimensions. Set vector_index_type='gsdiskann'."
        )
    if maxconn < minconn:
        raise ValueError("maxconn must be >= minconn")
    if not isinstance(schema_name, str) or not _IDENTIFIER_RE.match(schema_name):
        raise ValueError("schema_name must be a safe identifier using letters, numbers, and underscores")


class GaussDBConfig(BaseModel):
    # Connection
    database: str = Field("postgres", description="GaussDB database name")
    collection_name: str = Field("mem0", description="Name of the collection table")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    user: Optional[str] = Field(None, description="Database user")
    password: Optional[str] = Field(None, description="Database password")
    host: Optional[str] = Field(None, description="Database host")
    port: Optional[int] = Field(None, description="Database port")
    connection_string: Optional[str] = Field(
        None, description="GaussDB connection string (overrides host/port/user/password)"
    )
    sslmode: Optional[str] = Field(None, description="SSL mode (e.g., require, prefer, disable)")
    sslrootcert: Optional[str] = Field(None, description="SSL root certificate path")
    schema_name: str = Field("public", description="Optional advanced schema name; defaults to public")
    minconn: int = Field(1, description="Minimum number of connections in the pool")
    maxconn: int = Field(5, description="Maximum number of connections in the pool")
    insert_batch_size: int = Field(2000, description="Maximum number of rows per MERGE batch during insert")
    vector_index_maintenance_work_mem: Optional[str] = Field(
        None,
        description="Optional memory target used only during vector index creation, for example '256MB' or '2GB'",
    )

    # Deployment & Vector
    deployment_mode: str = Field(
        "centralized",
        description="GaussDB deployment mode: centralized or distributed",
    )
    vector_index_type: str = Field("gsdiskann", description="Vector index type: gsdiskann or gsivfflat")
    vector_metric: str = Field("cosine", description="Vector metric: cosine or l2")

    # Operational
    auto_create: bool = Field(True, description="Automatically create collection on init if it does not exist")

    @model_validator(mode="before")
    @classmethod
    def resolve_env_and_validate(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        for field, env_names in _ENV_DEFAULTS.items():
            if not values.get(field):
                env_val = _first_env(*env_names)
                if env_val:
                    values[field] = env_val

        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. "
                f"Allowed fields: {', '.join(sorted(allowed_fields))}"
            )

        for field in ("deployment_mode", "vector_index_type", "vector_metric"):
            if isinstance(values.get(field), str):
                values[field] = values[field].lower()

        collection_name = values.get("collection_name")
        if collection_name is not None and (
            not isinstance(collection_name, str) or not _IDENTIFIER_RE.match(collection_name)
        ):
            raise ValueError("collection_name must be a safe identifier using letters, numbers, and underscores")

        if not values.get("connection_string"):
            user, password = values.get("user"), values.get("password")
            host, port = values.get("host"), values.get("port")
            if bool(user) != bool(password):
                raise ValueError(
                    "When 'connection_string' is not provided, both 'user' and 'password' must be provided together."
                )
            if not user and not password:
                raise ValueError("Either 'connection_string' or both 'user' and 'password' must be provided.")
            if bool(host) != bool(port):
                raise ValueError(
                    "When 'connection_string' is not provided, both 'host' and 'port' must be provided together."
                )
            if not host and not port:
                raise ValueError("Either 'connection_string' or both 'host' and 'port' must be provided.")
        return values

    @model_validator(mode="after")
    def validate_values(self):
        self.vector_index_maintenance_work_mem = _normalize_memory_setting(
            self.vector_index_maintenance_work_mem,
            "vector_index_maintenance_work_mem",
        )
        validate_gaussdb_static_options(
            embedding_model_dims=self.embedding_model_dims,
            insert_batch_size=self.insert_batch_size,
            minconn=self.minconn,
            maxconn=self.maxconn,
            schema_name=self.schema_name,
            deployment_mode=self.deployment_mode,
            vector_index_type=self.vector_index_type,
            vector_metric=self.vector_metric,
        )
        return self

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)
