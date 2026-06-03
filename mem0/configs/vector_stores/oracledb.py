"""Pydantic configuration for the Oracle AI Vector Search integration."""

import re
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


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


ALLOWED_DISTANCE_METRICS = {"EUCLIDEAN", "EUCLIDEAN_SQUARED", "COSINE", "DOT", "HAMMING", "MANHATTAN"}
ALLOWED_INDEX_TYPES = {"HNSW", "IVF"}
ALLOWED_HNSW_INDEX_PARAMETERS = {"neighbors", "efconstruction"}
ALLOWED_IVF_INDEX_PARAMETERS = {"neighbor_partitions", "samples_per_partition", "min_vectors_per_partition"}


def _validate_int_parameter(parameters: dict, key: str, min_value: int, max_value: Optional[int] = None) -> None:
    if key not in parameters:
        return

    value = parameters[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"`index_parameters.{key}` must be an integer")
    if value < min_value:
        raise ValueError(f"`index_parameters.{key}` must be at least {min_value}")
    if max_value is not None and value > max_value:
        raise ValueError(f"`index_parameters.{key}` must be at most {max_value}")
    parameters[key] = int(value)


def _validate_index_parameters(index_type: str, index_parameters: Optional[dict]) -> Optional[dict]:
    if index_parameters is None:
        return None
    if not isinstance(index_parameters, dict):
        raise ValueError("`index_parameters` must be a dictionary")

    parameters = dict(index_parameters)
    invalid_keys = [key for key in parameters if not isinstance(key, str)]
    if invalid_keys:
        raise ValueError(
            "`index_parameters` keys must be strings: {}".format(
                ", ".join(sorted(repr(key) for key in invalid_keys))
            )
        )

    allowed_parameters = ALLOWED_HNSW_INDEX_PARAMETERS if index_type == "HNSW" else ALLOWED_IVF_INDEX_PARAMETERS
    extra_parameters = set(parameters) - allowed_parameters
    if extra_parameters:
        raise ValueError(
            "`index_parameters` contains unsupported keys for {}: {}".format(
                index_type, ", ".join(sorted(extra_parameters))
            )
        )

    if index_type == "HNSW":
        _validate_int_parameter(parameters, "neighbors", 2, 2048)
        _validate_int_parameter(parameters, "efconstruction", 1, 65535)
    else:
        _validate_int_parameter(parameters, "neighbor_partitions", 1, 10000000)
        _validate_int_parameter(parameters, "samples_per_partition", 1)
        _validate_int_parameter(parameters, "min_vectors_per_partition", 0)

    return parameters


class OracleAIVectorSearchConfig(BaseModel):
    """Configuration required to connect to an Oracle database with vector search enabled."""

    connection_params: Optional[dict] = Field(None, description="Database connection parameters, including auth.")
    use_connection_pool: Optional[bool] = Field(
        True, description="Oracle Connection or ConnectionPool (overrides connection string and individual parameters)"
    )

    client: Optional[Any] = Field(
        None, description="Oracle Connection or ConnectionPool (overrides connection string and individual parameters)"
    )

    collection_name: Optional[str] = Field("mem0", description="Default name for the collection")
    embedding_model_dims: int = Field(1536, description="Dimension of the embedding vectors")
    distance_metric: Optional[str] = Field(
        "COSINE",
        description="Similarity metric: EUCLIDEAN, EUCLIDEAN_SQUARED, COSINE, DOT, HAMMING or MANHATTAN. Defaults to COSINE",
    )

    do_create_index: Optional[bool] = Field(True, description="Optional whether to create index")
    index_type: Optional[str] = Field("HNSW", description="Optional index type, HNSW or IVF")
    index_name: Optional[str] = Field(None, description="Optional custom name for the vector index")
    index_parameters: Optional[dict] = Field(
        None,
        description="Optional structured CREATE VECTOR INDEX parameters",
    )
    index_accuracy: Optional[int] = Field(None, description="Optional index accuracy")

    @model_validator(mode="after")
    def _validate_model(self):
        """Normalise attributes and validate identifiers/metrics."""

        if not self.connection_params and not self.client:
            raise ValueError("Must provide at least one of `connection_params` and `client`")

        if self.distance_metric is None:
            raise ValueError("`distance_metric` must not be None")
        distance_metric = self.distance_metric.upper()
        if distance_metric not in ALLOWED_DISTANCE_METRICS:
            raise ValueError(f"`distance_metric` must be one of: {ALLOWED_DISTANCE_METRICS}")
        self.distance_metric = distance_metric

        if self.index_type is None:
            raise ValueError("`index_type` must not be None")
        index_type = self.index_type.upper()
        if index_type not in ALLOWED_INDEX_TYPES:
            raise ValueError(f"`index_type` must be one of: {ALLOWED_INDEX_TYPES}")
        self.index_type = index_type

        if self.index_name is None:
            self.index_name = f"{self.collection_name}_VEC_IDX"

        self.index_name = _quote_identifier(self.index_name)
        self.collection_name = _quote_identifier(self.collection_name)

        self.index_parameters = _validate_index_parameters(self.index_type, self.index_parameters)

        if self.index_accuracy and not (0 < self.index_accuracy <= 100):
            raise ValueError("`index_accuracy` must be between 1 and 100")

        if not (0 < self.embedding_model_dims):
            raise ValueError("`embedding_model_dims` must be bigger than 0")

        return self

    def canonical_index_parameters(self) -> Optional[dict]:
        return _validate_index_parameters(self.index_type, self.index_parameters)

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
