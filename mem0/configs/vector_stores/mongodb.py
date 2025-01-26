from typing import Any, Dict, Optional, Callable, List

from pydantic import BaseModel, Field, root_validator


class MongoVectorConfig(BaseModel):
    dbname: str = Field("mydatabase", description="Name of the MongoDB database")
    collection_name: str = Field("mycollection", description="Name of the MongoDB collection")
    mdb_uri: str = Field(..., description="MongoDB connection URI")
    get_embedding: Callable[[str], List[float]] = Field(..., description="Function to get embedding for a given text")
    embedding_model_dims: int = Field(..., description="Dimensions of the embedding model")
    
    @root_validator(pre=True)
    def validate_mdb_uri(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensures that the 'mdb_uri' field is provided.
        """
        mdb_uri = values.get("mdb_uri")
        if not mdb_uri:
            raise ValueError("The 'mdb_uri' must be provided.")
        return values

    @root_validator(pre=True)
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prevents any fields other than the ones declared on the model.
        """
        allowed_fields = set(cls.__fields__)
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. "
                f"Please provide only the following fields: {', '.join(allowed_fields)}."
            )
        return values
