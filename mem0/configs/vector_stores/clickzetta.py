from typing import Any, Dict, Literal, Optional
import warnings

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Suppress schema field name warning
warnings.filterwarnings("ignore", message=".*Field name.*schema.*shadows.*")


class ClickzettaConfig(BaseModel):
    """ClickZetta Vector Store Configuration."""
    
    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())
    
    collection_name: str = Field("mem0", description="Collection/table name")
    embedding_model_dims: Optional[int] = Field(1536, description="Embedding vector dimensions")
    service: str = Field(..., description="ClickZetta service address")
    instance: str = Field(..., description="Instance name")
    workspace: str = Field(..., description="Workspace name")
    schema: str = Field(..., description="Schema name")
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")
    vcluster: str = Field(..., description="Virtual cluster name")
    protocol: str = Field("http", description="Connection protocol (http/https)")
    distance_metric: Literal["cosine", "euclidean", "dot_product"] = Field(
        "cosine", description="Distance metric"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_required_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        required_fields = ["service", "instance", "workspace", "schema", "username", "password", "vcluster"]
        missing = [f for f in required_fields if not values.get(f)]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")
        return values
