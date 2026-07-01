from typing import Optional

from pydantic import BaseModel, Field


class DakeraConfig(BaseModel):
    """Configuration for the Dakera self-hosted vector memory store.

    Dakera is a decay-weighted, self-hosted vector memory server that handles
    embedding internally. Unlike other vector stores, you do not need to configure
    embedding dimensions — Dakera manages its own embedding pipeline.

    Quick-start:
        docker run -d -p 3300:3300 -e DAKERA_API_KEY=demo \\
            ghcr.io/dakera-ai/dakera:latest

    See https://dakera.ai for full documentation.
    """

    collection_name: str = Field(
        default="mem0",
        description="Maps to the agent_id namespace in Dakera. All memories stored "
        "by this instance are scoped to this namespace.",
    )
    url: str = Field(
        default="http://localhost:3300",
        description="Base URL of the self-hosted Dakera server (no trailing slash).",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="Dakera API key. Required when the server is started with "
        "DAKERA_API_KEY set. Omit or set to None for unauthenticated local dev.",
    )
    # mem0 internally calls create_col(vector_size=...) — we accept but ignore the
    # dimension because Dakera owns its own embedding model.
    embedding_model_dims: Optional[int] = Field(
        default=None,
        description="Accepted for API compatibility with mem0 internals; Dakera manages "
        "its own embedding pipeline so this value is not used.",
    )
