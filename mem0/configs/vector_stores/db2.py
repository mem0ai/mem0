"""Pydantic configuration for the IBM Db2 vector store integration."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator

# Distance metrics supported by the Db2 ANN vector index.
# HAMMING, MANHATTAN, and DOT use exact scan — ANN index not available for them.
_ANN_SUPPORTED_METRICS = {"COSINE", "EUCLIDEAN", "EUCLIDEAN_DISTANCE"}


class Db2Config(BaseModel):
    """Configuration required to connect to an IBM Db2 database with vector search enabled.

    Either ``client`` (an existing ``ibm_db_dbi.Connection``) or
    ``connection_params`` must be provided.

    ``connection_params`` keys:
        database (str): Db2 database name.
        host (str): Hostname or IP of the Db2 server.  Mapped to the ibm_db
            connection-string keyword ``HOSTNAME`` (not ``HOST``) when the
            connection string is built internally.
        port (str | int): Port number (default ``50000``).
        username (str): Db2 user.  Mapped to the ibm_db keyword ``UID``.
        password (str): Db2 password.  Mapped to the ibm_db keyword ``PWD``.
        security (str, optional): SSL/TLS mode string, e.g. ``"SSL"``.  Mapped to ``SECURITY=<value>``.
        ssl_cert (str, optional): Path to the server certificate (.arm/.pem).
            Mapped to ``SSLServerCertificate``.

    Connection pooling note:
        ``ibm_db_dbi`` does not provide a built-in pool.  For multi-threaded
        deployments, manage a pool externally and pass the per-request
        connection via the ``client`` parameter.
    """

    client: Optional[Any] = Field(
        None,
        description="Existing ibm_db_dbi.Connection (overrides connection_params)",
    )
    connection_params: Optional[Dict[str, Any]] = Field(
        None,
        description="Connection parameters dict with keys: database, host, port, username, password",
    )

    collection_name: str = Field("mem0", description="Db2 table name used as the vector store collection")
    embedding_model_dims: int = Field(1536, description="Dimension of the embedding vectors", gt=0)
    distance_strategy: str = Field(
        "EUCLIDEAN",
        description=(
            "Distance function: EUCLIDEAN (default), COSINE, DOT, "
            "EUCLIDEAN_DISTANCE, HAMMING, or MANHATTAN"
        ),
    )

    use_vector_index: bool = Field(
        False,
        description=(
            "Create a native Db2 ANN vector index (CREATE VECTOR INDEX) for "
            "approximate nearest-neighbour search.  Requires Db2 12.1.5+.  "
            "Only compatible with COSINE, EUCLIDEAN, and EUCLIDEAN_DISTANCE — "
            "not HAMMING, MANHATTAN, or DOT.  Defaults to False (exact scan, "
            "works on all versions >= 12.1.2).  "
            "PRODUCTION DEPLOYMENTS ONLY: requires Db2 Standard/Advanced "
            "Edition or Db2 on IBM Cloud/watsonx.data.  Do NOT use with Db2 "
            "Community Edition (CE) containers (Podman/Docker) — CE drops TCP "
            "connections after CREATE VECTOR INDEX due to in-memory ANN graph "
            "reconstruction.  Keep False (the default) on CE containers."
        ),
    )

    # Named db_schema to avoid shadowing Pydantic BaseModel.schema().
    db_schema: Optional[str] = Field(
        None,
        description=(
            "Optional Db2 schema name.  When set, ``SET SCHEMA <name>`` is "
            "issued immediately after the connection is established so all "
            "unqualified table references resolve to this schema."
        ),
    )

    text_field: str = Field("text", description="Column name for the raw text (CLOB)")
    text_lemmatized_field: str = Field(
        "text_lemmatized",
        description=(
            "Column name for pre-processed (stemmed/lemmatized) text (CLOB). "
            "Populated from payload['text_lemmatized'] on insert/update. "
            "Used by keyword_search() with Db2 Text Search for higher recall."
        ),
    )
    id_field: str = Field("id", description="Column name for the primary key (VARCHAR 36)")
    metadata_field: str = Field("metadata", description="Column name for JSON metadata (BLOB)")
    embedding_field: str = Field("embedding", description="Column name for the vector (FLOAT32)")

    @model_validator(mode="after")
    def _require_connection(self) -> "Db2Config":
        if self.client is None and not self.connection_params:
            raise ValueError("Either `client` or `connection_params` must be provided.")

        valid = {"EUCLIDEAN", "COSINE", "DOT", "EUCLIDEAN_DISTANCE", "HAMMING", "MANHATTAN"}
        if self.distance_strategy.upper() not in valid:
            raise ValueError(f"`distance_strategy` must be one of {valid}; got '{self.distance_strategy}'")
        self.distance_strategy = self.distance_strategy.upper()

        # ANN index is only supported for COSINE, EUCLIDEAN, EUCLIDEAN_DISTANCE.
        if self.use_vector_index and self.distance_strategy not in _ANN_SUPPORTED_METRICS:
            raise ValueError(
                f"use_vector_index=True is not compatible with "
                f"distance_strategy='{self.distance_strategy}'. "
                f"The Db2 ANN index only supports COSINE, EUCLIDEAN, and "
                f"EUCLIDEAN_DISTANCE. Set use_vector_index=False for "
                f"{self.distance_strategy}."
            )

        return self

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        allowed_fields = set(cls.model_fields.keys())
        extra_fields = set(values.keys()) - allowed_fields
        if extra_fields:
            raise ValueError(
                "Extra fields not allowed: {}. Please input only the following fields: {}".format(
                    ", ".join(sorted(extra_fields)), ", ".join(sorted(allowed_fields))
                )
            )
        return values
