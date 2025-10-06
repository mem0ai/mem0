from typing import Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

from mem0.llms.configs import LlmConfig


class Neo4jConfig(BaseModel):
    url: Optional[str] = Field(None, description="Host address for the graph database")
    username: Optional[str] = Field(None, description="Username for the graph database")
    password: Optional[str] = Field(None, description="Password for the graph database")
    database: Optional[str] = Field(None, description="Database for the graph database")
    base_label: Optional[bool] = Field(None, description="Whether to use base node label __Entity__ for all entities")

    @model_validator(mode="before")
    def check_host_port_or_path(cls, values):
        url, username, password = (
            values.get("url"),
            values.get("username"),
            values.get("password"),
        )
        if not url or not username or not password:
            raise ValueError("Please provide 'url', 'username' and 'password'.")
        return values


class MemgraphConfig(BaseModel):
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
            raise ValueError("Please provide 'url', 'username' and 'password'.")
        return values


class NeptuneConfig(BaseModel):
    app_id: Optional[str] = Field("Mem0", description="APP_ID for the connection")
    endpoint: Optional[str] = (
        Field(
            None,
            description="Endpoint to connect to a Neptune-DB Cluster as 'neptune-db://<host>' or Neptune Analytics Server as 'neptune-graph://<graphid>'",
        ),
    )
    base_label: Optional[bool] = Field(None, description="Whether to use base node label __Entity__ for all entities")
    collection_name: Optional[str] = Field(None, description="vector_store collection name to store vectors when using Neptune-DB Clusters")

    @model_validator(mode="before")
    def check_host_port_or_path(cls, values):
        endpoint = values.get("endpoint")
        if not endpoint:
            raise ValueError("Please provide 'endpoint' with the format as 'neptune-db://<endpoint>' or 'neptune-graph://<graphid>'.")
        if endpoint.startswith("neptune-db://"):
            # This is a Neptune DB Graph
            return values
        elif endpoint.startswith("neptune-graph://"):
            # This is a Neptune Analytics Graph
            graph_identifier = endpoint.replace("neptune-graph://", "")
            if not graph_identifier.startswith("g-"):
                raise ValueError("Provide a valid 'graph_identifier'.")
            values["graph_identifier"] = graph_identifier
            return values
        else:
            raise ValueError(
                "You must provide an endpoint to create a NeptuneServer as either neptune-db://<endpoint> or neptune-graph://<graphid>"
            )


class KuzuConfig(BaseModel):
    db: Optional[str] = Field(":memory:", description="Path to a Kuzu database file")


class GraphStoreConfig(BaseModel):
    provider: str = Field(
        description="Provider of the data store (e.g., 'neo4j', 'memgraph', 'neptune', 'kuzu')",
        default="neo4j",
    )
    config: Union[Neo4jConfig, MemgraphConfig, NeptuneConfig, KuzuConfig] = Field(
        description="Configuration for the specific data store", default=None
    )
    llm: Optional[LlmConfig] = Field(description="LLM configuration for querying the graph store", default=None)
    custom_prompt: Optional[str] = Field(
        description="Custom prompt to fetch entities from the given text", default=None
    )

    @field_validator("config")
    def validate_config(cls, v, values):
        provider = values.data.get("provider")
        if provider == "neo4j":
            return Neo4jConfig(**v.model_dump())
        elif provider == "memgraph":
            return MemgraphConfig(**v.model_dump())
        elif provider == "neptune" or provider == "neptunedb":
            return NeptuneConfig(**v.model_dump())
        elif provider == "kuzu":
            return KuzuConfig(**v.model_dump())
        else:
            raise ValueError(f"Unsupported graph store provider: {provider}")
