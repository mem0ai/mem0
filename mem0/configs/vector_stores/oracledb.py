"""Pydantic configuration for the Oracle AI Vector Search integration."""

import re
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _quote_identifier(name: str) -> str:
    name = name.strip()
    reg = r'^(?:"[^"]+"|[^".]+)(?:\.(?:"[^"]+"|[^".]+))*$'
    pattern_validate = re.compile(reg)

    if not pattern_validate.match(name):
        raise ValueError(f"Identifier name {name} is not valid.")

    pattern_match = r'"([^"]+)"|([^".]+)'
    groups = re.findall(pattern_match, name)
    groups = [m[0] or m[1] for m in groups]
    groups = [f'"{g}"' for g in groups]

    return ".".join(groups)


class HnswParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    neighbors: Optional[int] = Field(None, ge=2, le=2048)
    efconstruction: Optional[int] = Field(None, ge=1, le=65535)


class IvfParams(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    neighbor_partitions: Optional[int] = Field(None, alias="neighbor partitions", ge=1, le=10_000_000)
    samples_per_partition: Optional[int] = Field(None, ge=1)
    min_vectors_per_partition: Optional[int] = Field(None, ge=0)


class OracleAIVectorSearchConfig(BaseModel):
    """Configuration required to connect to an Oracle database with vector search enabled."""

    connection_params: Optional[dict] = Field(None, description="Database connection parameters, including auth.")
    use_connection_pool: bool = Field(
        True,
        description="Create a ConnectionPool instead of a single Connection when no client is provided",
    )

    client: Optional[Any] = Field(
        None, description="Oracle Connection or ConnectionPool (overrides connection string and individual parameters)"
    )

    collection_name: str = Field("mem0", description="Default name for the collection")
    embedding_model_dims: int = Field(1536, description="Dimension of the embedding vectors")
    distance_metric: Literal["EUCLIDEAN", "EUCLIDEAN_SQUARED", "COSINE", "DOT", "HAMMING", "MANHATTAN"] = Field(
        "COSINE",
        description="Similarity metric: EUCLIDEAN, EUCLIDEAN_SQUARED, COSINE, DOT, HAMMING or MANHATTAN. Defaults to COSINE",
    )

    do_create_index: Optional[bool] = Field(True, description="Optional whether to create index")
    index_type: Literal["HNSW", "IVF"] = Field("HNSW", description="Optional index type, HNSW or IVF")
    index_name: Optional[str] = Field(None, description="Optional custom name for the vector index")
    index_parameters: Optional[dict] = Field(
        None,
        description="Optional structured CREATE VECTOR INDEX parameters",
    )
    index_accuracy: Optional[int] = Field(None, description="Optional index accuracy")

    @field_validator("distance_metric", "index_type", mode="before")
    @classmethod
    def _normalize_uppercase(cls, value: Any) -> Any:
        return value.upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _validate_model(self):
        """Normalise attributes and validate identifiers/metrics."""

        if not self.connection_params and not self.client:
            raise ValueError("Must provide at least one of `connection_params` and `client`")

        if self.index_name is None:
            self.index_name = f"{self.collection_name}_VEC_IDX"

        self.index_name = _quote_identifier(self.index_name)
        self.collection_name = _quote_identifier(self.collection_name)

        if self.index_parameters is not None:
            parameter_model = HnswParams if self.index_type == "HNSW" else IvfParams
            self.index_parameters = parameter_model.model_validate(self.index_parameters).model_dump(
                by_alias=True,
                exclude_none=True,
            )

        if self.index_accuracy and not (0 < self.index_accuracy <= 100):
            raise ValueError("`index_accuracy` must be between 1 and 100")

        if not (0 < self.embedding_model_dims):
            raise ValueError("`embedding_model_dims` must be bigger than 0")

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
