from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class GoogleMatchingEngineConfig(BaseModel):
    project_id: str = Field(description="Google Cloud project ID")
    project_number: str = Field(description="Google Cloud project number")
    region: str = Field(description="Google Cloud region")
    endpoint_id: str = Field(description="Vertex AI Vector Search endpoint ID")
    index_id: str = Field(description="Vertex AI Vector Search index ID")
    deployment_index_id: str = Field(description="Deployment-specific index ID")
    collection_name: Optional[str] = Field(None, description="Collection name, defaults to index_id")
    credentials_path: Optional[str] = Field(None, description="Path to service account credentials file")
    vector_search_api_endpoint: Optional[str] = Field(None, description="Vector search API endpoint")

    model_config = ConfigDict(extra="forbid")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.collection_name:
            self.collection_name = self.index_id

    def model_post_init(self, _context) -> None:
        """Set collection_name to index_id if not provided"""
        if self.collection_name is None:
            self.collection_name = self.index_id
