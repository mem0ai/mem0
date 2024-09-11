from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from mem0.llms.configs import LlmConfig


class Neo4jConfig(BaseModel):
    url: Optional[str] = Field(None, description="Host address for the graph database")
    username: Optional[str] = Field(None, description="Username for the graph database")
    password: Optional[str] = Field(None, description="Password for the graph database")

    @model_validator(mode="before")
    def check_host_port_or_path(cls, values):
        url, username, password = (
            values.get("url"),
            values.get("username"),
            values.get("password"),
        )
        if not url or not username or not password:
            raise ValueError(
                "Please provide 'url', 'username' and 'password'."
            )
        return values
    
class FalkorDBConfig(BaseModel):
    database: Optional[str] = Field(None, description="Database name for the graph database")
    host: Optional[str] = Field(None, description="Host address for the graph database")
    username: Optional[str] = Field(None, description="Username for the graph database")
    password: Optional[str] = Field(None, description="Password for the graph database")
    port: Optional[int] = Field(None, description="Port for the graph database")

    @model_validator(mode="before")
    def check_host_port_or_path(cls, values):
        database, host, username, password, port = (
            values.get("database"),
            values.get("host"),
            values.get("username"),
            values.get("password"),
            values.get("port"),
        )
        if not database or not host or not username or not password or not port:
            raise ValueError(
                "Please provide 'database', 'host', 'username', 'password' and 'port'."
            )
        return values


class GraphStoreConfig(BaseModel):
    provider: str = Field(
        description="Provider of the data store (e.g., 'falkordb', 'neo4j')", 
        default="falkordb"
    )
    config: FalkorDBConfig = Field(
        description="Configuration for the specific data store",
        default=None
    )
    llm: Optional[LlmConfig] = Field(
        description="LLM configuration for querying the graph store",
        default=None
    )
    custom_prompt: Optional[str] = Field(
        description="Custom prompt to fetch entities from the given text",
        default=None
    )

    @field_validator("config")
    def validate_config(cls, v, values):
        provider = values.data.get("provider")
        if provider == "neo4j":
            return Neo4jConfig(**v.model_dump())
        elif provider == "falkordb":
            return FalkorDBConfig(**v.model_dump())
        else:
            raise ValueError(f"Unsupported graph store provider: {provider}")
        
