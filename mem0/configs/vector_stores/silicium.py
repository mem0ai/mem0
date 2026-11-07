# SPDX-License-Identifier: Apache-2.0
"""Configuration model for the Silicium in-process HNSW and 64-byte aligned vector store backend."""

from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

_MAX_TENANT_SCOPES = 256
_MAX_ENTRIES_PER_TENANT = 1024
_MAX_VECTOR_DIM = 65536
_SUPPORTED_DISTANCE_STRATEGIES = frozenset({"cosine", "euclidean", "inner_product"})


class SiliciumConfig(BaseModel):
    """Pydantic configuration for ``SiliciumDB`` vector store in Mem0."""

    collection_name: str = Field("mem0", description="Default name for the collection")
    embedding_model_dims: int = Field(1536, description="Dimension of the embedding vector")
    path: Optional[str] = Field(None, description="Optional directory or file path for JSON persistence")
    distance_strategy: str = Field(
        "cosine",
        description="Distance strategy to use. Options: 'cosine', 'euclidean', 'inner_product'",
    )
    max_tenant_scopes: int = Field(
        _MAX_TENANT_SCOPES,
        description="Maximum number of isolated collections retained in the in-process arena",
    )

    @model_validator(mode="before")
    @classmethod
    def validate_distance_strategy_and_bounds(cls, values: Dict[str, object]) -> Dict[str, object]:
        """Validate ``distance_strategy``, ``embedding_model_dims``, and ``max_tenant_scopes`` bounds."""
        if not isinstance(values, dict):
            return values
        distance_strategy = values.get("distance_strategy")
        if distance_strategy is not None:
            norm_strategy = str(distance_strategy).strip().lower()
            if norm_strategy not in _SUPPORTED_DISTANCE_STRATEGIES:
                raise ValueError(
                    "Invalid distance_strategy. Must be one of: 'cosine', 'euclidean', 'inner_product'"
                )
            values = {**values, "distance_strategy": norm_strategy}

        if "embedding_model_dims" in values and values["embedding_model_dims"] is not None:
            raw_dims = values["embedding_model_dims"]
            dims = int(raw_dims) if isinstance(raw_dims, (int, float, str)) else 0
            if dims <= 0 or dims > _MAX_VECTOR_DIM:
                raise ValueError(
                    f"Invalid embedding_model_dims: must be between 1 and {_MAX_VECTOR_DIM}, got {dims}"
                )
            values = {**values, "embedding_model_dims": dims}

        if "max_tenant_scopes" in values and values["max_tenant_scopes"] is not None:
            raw_scopes = values["max_tenant_scopes"]
            scopes = int(raw_scopes) if isinstance(raw_scopes, (int, float, str)) else 0
            if scopes <= 0 or scopes > _MAX_TENANT_SCOPES:
                raise ValueError(
                    f"Invalid max_tenant_scopes: must be between 1 and {_MAX_TENANT_SCOPES}, got {scopes}"
                )
            values = {**values, "max_tenant_scopes": scopes}

        return values

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, object]) -> Dict[str, object]:
        """Reject unknown configuration keys with a clear ``ValueError``."""
        if not isinstance(values, dict):
            return values
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(sorted(extra_fields))}. "
                f"Please input only the following fields: {', '.join(sorted(allowed_fields))}"
            )
        return values

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
