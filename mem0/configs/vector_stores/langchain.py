from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class LangchainConfig(BaseModel):
    try:
        from langchain_community.vectorstores import VectorStore
    except ImportError:
        raise ImportError(
            "The 'langchain_community' library is required. Please install it using 'pip install langchain_community'."
        )
    VectorStore: ClassVar[type] = VectorStore

    client: VectorStore = Field(description="Existing VectorStore instance")
    collection_name: str = Field("mem0", description="Name of the collection to use")

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")
