from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Db2Config(BaseModel):
    # Connection parameters
    database: Optional[str] = Field(None, description="Db2 database name")
    host: Optional[str] = Field(None, description="Db2 host")
    port: Optional[int] = Field(50000, description="Db2 port")
    username: Optional[str] = Field(None, description="Db2 username")
    password: Optional[str] = Field(None, description="Db2 password")
    ssl: Optional[bool] = Field(False, description="Whether to use SSL")
    connection_string: Optional[str] = Field(None, description="Raw Db2 connection string")
    
    # Alternatively, an existing connection object
    client: Optional[Any] = Field(None, description="Existing ibm_db_dbi connection object")
    
    # Table and column configuration
    table_name: str = Field("mem0", description="Name of the table to store vectors")
    id_field: str = Field("id", description="Name of the ID column")
    text_field: str = Field("text", description="Name of the text column")
    metadata_field: str = Field("metadata", description="Name of the metadata JSON column")
    embedding_field: str = Field("embedding", description="Name of the vector embedding column")
    
    # Distance strategy
    distance_strategy: Literal["EUCLIDEAN", "COSINE", "DOT"] = Field(
        "COSINE", description="Distance strategy (EUCLIDEAN, COSINE, DOT)"
    )

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    @model_validator(mode="before")
    def validate_connection(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        client = values.get("client")
        if client:
            return values
        
        conn_string = values.get("connection_string")
        if conn_string:
            return values
            
        db = values.get("database")
        host = values.get("host")
        user = values.get("username")
        pw = values.get("password")
        
        if not (db and host and user and pw):
            raise ValueError(
                "Either 'client', 'connection_string', or all of "
                "('database', 'host', 'username', 'password') must be provided."
            )
            
        return values
