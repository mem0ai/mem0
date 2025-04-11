from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class AzureAISearchConfig(BaseModel):
    collection_name: str = Field("mem0", description="Name of the collection")
    service_name: str = Field(None, description="Azure AI Search service name")
    api_key: str = Field(None, description="API key for the Azure AI Search service")
    embedding_model_dims: int = Field(None, description="Dimension of the embedding vector")
    compression_type: Optional[str] = Field(
        None, description="Type of vector compression to use. Options: 'scalar', 'binary', or None"
    )
    use_float16: bool = Field(
        False,
        description="Whether to store vectors in half precision (Edm.Half) instead of full precision (Edm.Single)",
    )
    hybrid_search: bool = Field(
        False, description="Whether to use hybrid search. If True, vector_filter_mode must be 'preFilter'"
    )
    vector_filter_mode: Optional[str] = Field(
        "preFilter", description="Mode for vector filtering. Options: 'preFilter', 'postFilter'"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields

        # Check for use_compression to provide a helpful error
        if "use_compression" in extra_fields:
            raise ValueError(
                "The parameter 'use_compression' is no longer supported. "
                "Please use 'compression_type=\"scalar\"' instead of 'use_compression=True' "
                "or 'compression_type=None' instead of 'use_compression=False'."
            )

        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. "
                f"Please input only the following fields: {', '.join(allowed_fields)}"
            )

        # Validate compression_type values
        if "compression_type" in values and values["compression_type"] is not None:
            valid_types = ["scalar", "binary"]
            if values["compression_type"].lower() not in valid_types:
                raise ValueError(
                    f"Invalid compression_type: {values['compression_type']}. "
                    f"Must be one of: {', '.join(valid_types)}, or None"
                )

        return values

    model_config = {
        "arbitrary_types_allowed": True,
    }
