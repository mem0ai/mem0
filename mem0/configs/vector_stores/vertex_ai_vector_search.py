from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GoogleMatchingEngineConfig(BaseModel):
    project_id: str = Field(description="Google Cloud project ID")
    project_number: str = Field(description="Google Cloud project number")
    region: str = Field(description="Google Cloud region")
    endpoint_id: str = Field(description="Vertex AI Vector Search endpoint ID")
    index_id: str = Field(description="Vertex AI Vector Search index ID")
    deployment_index_id: str = Field(description="Deployment-specific index ID")
    collection_name: Optional[str] = Field(None, description="Collection name, defaults to index_id")
    credentials_path: Optional[str] = Field(None, description="Path to service account credentials JSON file")
    service_account_json: Optional[Dict] = Field(None, description="Service account credentials as dictionary (alternative to credentials_path)")
    vector_search_api_endpoint: Optional[str] = Field(None, description="Vector search API endpoint")
    distance_metric: str = Field(
        "cosine",
        description=(
            "Distance measure of the deployed Vertex AI index: 'cosine' (default), "
            "'dot_product' (aliases: 'dot_product_point', 'inner_product', 'ip'), or "
            "'squared_l2' (aliases: 'squared_l2_distance', 'euclidean', 'l2'). "
            "mem0 cannot infer this from the deployed index, so set it to match."
        ),
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("distance_metric")
    @classmethod
    def _normalize_distance_metric(cls, value: str) -> str:
        """Canonicalize common spellings of the Vertex AI distance measure types."""
        aliases = {
            "cosine": "cosine",
            "dot_product": "dot_product",
            "dotproduct": "dot_product",
            "dot_product_point": "dot_product",
            "inner_product": "dot_product",
            "ip": "dot_product",
            "euclidean": "squared_l2",
            "l2": "squared_l2",
            "squared_l2": "squared_l2",
            "squared_l2_distance": "squared_l2",
        }
        normalized = aliases.get(value.strip().lower())
        if normalized is None:
            raise ValueError(
                f"Invalid distance_metric '{value}'. Expected one of: "
                f"'cosine', 'dot_product' (or 'dot_product_point', 'inner_product', 'ip'), "
                f"'squared_l2' (or 'squared_l2_distance', 'euclidean', 'l2')."
            )
        return normalized

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.collection_name:
            self.collection_name = self.index_id

    def model_post_init(self, _context) -> None:
        """Set collection_name to index_id if not provided"""
        if self.collection_name is None:
            self.collection_name = self.index_id
