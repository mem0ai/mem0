"""
Configuration for Amazon Neptune Analytics vector store.

This module provides configuration settings for integrating with Amazon Neptune Analytics
as a vector store backend for Mem0's memory layer.
"""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Rejecting any identifier that doesn't match this pattern is what keeps the
# f-string label interpolations in mem0/vector_stores/neptune_analytics.py safe.
_VALID_CYPHER_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class NeptuneAnalyticsConfig(BaseModel):
    """
    Configuration class for Amazon Neptune Analytics vector store.
    
    Amazon Neptune Analytics is a graph analytics engine that can be used as a vector store
    for storing and retrieving memory embeddings in Mem0.
    
    Attributes:
        collection_name (str): Name of the collection to store vectors. Defaults to "mem0".
        endpoint (str): Neptune Analytics graph endpoint URL or Graph ID for the runtime.
    """
    collection_name: str = Field("mem0", description="Default name for the collection")
    endpoint: str = Field("endpoint", description="Graph ID for the runtime")

    @field_validator("collection_name")
    def validate_collection_name(cls, v):
        if not _VALID_CYPHER_IDENTIFIER.match(v):
            raise ValueError(
                f"Invalid collection_name: {v!r}. Must start with a letter or underscore and "
                "contain only letters, digits, and underscores."
            )
        return v

    model_config = ConfigDict(arbitrary_types_allowed=False)
