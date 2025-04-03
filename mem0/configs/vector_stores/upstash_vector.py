import os
from typing import Any, ClassVar, Dict, Optional

from pydantic import BaseModel, Field, model_validator

try:
    from upstash_vector import Index
except ImportError:
    raise ImportError("The 'upstash_vector' library is required. Please install it using 'pip install upstash_vector'.")


class UpstashVectorConfig(BaseModel):
    Index: ClassVar[type] = Index

    url: Optional[str] = Field(None, description="URL for Upstash Vector index")
    token: Optional[str] = Field(None, description="Token for Upstash Vector index")
    client: Optional[Index] = Field(None, description="Existing `upstash_vector.Index` client instance")
    collection_name: str = Field("mem0", description="Namespace to use for the index")
    enable_embeddings: bool = Field(
        False, description="Whether to use built-in upstash embeddings or not. Default is True."
    )

    @model_validator(mode="before")
    @classmethod
    def check_credentials_or_client(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        client = values.get("client")
        url = values.get("url") or os.environ.get("UPSTASH_VECTOR_REST_URL")
        token = values.get("token") or os.environ.get("UPSTASH_VECTOR_REST_TOKEN")

        if not client and not (url and token):
            raise ValueError("Either a client or URL and token must be provided.")
        return values

    model_config = {
        "arbitrary_types_allowed": True,
    }
