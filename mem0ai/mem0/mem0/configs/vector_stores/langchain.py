from typing import Any, ClassVar, Dict

from pydantic import BaseModel, Field, model_validator


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

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. Please input only the following fields: {', '.join(allowed_fields)}"
            )
        return values

    model_config = {
        "arbitrary_types_allowed": True,
    }
