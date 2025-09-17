"""
Configuration for Amazon Neptune Analytics vector store.

This module provides configuration settings for integrating with Amazon Neptune Analytics
as a vector store backend for Mem0's memory layer.
"""

from pydantic import BaseModel, Field


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

    model_config = {
        "arbitrary_types_allowed": False,
    }
