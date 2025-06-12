import os
import json
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import logging
from app.database import get_db
from app.models import Config as ConfigModel
from app.utils.memory import reset_memory_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/config", tags=["config"])

class LLMConfig(BaseModel):
    model: str = Field(..., description="LLM model name")
    temperature: float = Field(..., description="Temperature setting for the model")
    max_tokens: int = Field(..., description="Maximum tokens to generate")
    api_key: Optional[str] = Field(None, description="API key or 'env:LLM_AZURE_OPENAI_API_KEY' to use environment variable")    
    azure_deployment: Optional[str] = Field(None, description="Deployment name for Azure OpenAI, othewise loaded from LLM_AZURE_DEPLOYMENT")
    api_version: Optional[str] = Field(None, description="API version for Azure OpenAI, otherwise loaded from LLM_AZURE_OPENAI_API_KEY")
    azure_endpoint: Optional[str] = Field(None, description="Endpoint URL for Azure OpenAI or Ollama server, otherwise loaded from LLM_AZURE_ENDPOINT")

class LLMProvider(BaseModel):
    provider: str = Field(..., description="LLM provider name")
    config: LLMConfig

class EmbedderConfig(BaseModel):
    model: str = Field(..., description="Embedder model name")
    api_key = Optional[str] = Field(None, description="Embedding API key or 'env:EMBEDDING_AZURE_OPENAI_API_KEY'")    
    azure_deployment = Optional[str] = Field(None,"Embedding deployment if not loaded from EMBEDDING_AZURE_DEPLOYMENT")
    azure_endpoint = Optional[str] = Field(None, description="Azure endpoint if not loaded from EMBEDDING_AZURE_ENDPOINT")
    api_version = Optional[str] = Field(None, description="Azure embedding API version if not loadedf from EMBEDDING_AZURE_API_VERSION")

class EmbedderProvider(BaseModel):
    provider: str = Field(..., description="Embedder provider name")
    config: EmbedderConfig

class OpenMemoryConfig(BaseModel):
    custom_instructions: Optional[str] = Field(None, description="Custom instructions for memory management and fact extraction")

class VectorProvider(BaseModel):
    host: str = Field(..., description="Host for the vector store")
    port: int = Field(..., description="Port for the vector store")
    dbname: str = Field(..., description="Database name for the vector store")
    user: str = Field(..., description="User for the vector store")
    password: str = Field(..., description="Password for the vector store")
    collectionName: str = Field(..., description="Collection name for the vector store")
    dimension: Optional[int] = Field(1536, ..., description="Dimension for the vector store")
    embeddingModelDims: Optional[int] = Field(1536, ..., description="Embedding model dimension for the vector store")
    hnsw: Optional[bool] = Field(True, ..., description="If HNSW indexing is available, defaults to True")
    diskMan: Optional[bool] = Field(False, ..., description="If Diskman algorithm is available, defaults to False")

class VectorStoreConfig(BaseModel):
    provider: str = Field(..., description="Vector store provider name")
    config: VectorProvider

class GraphProvider(BaseModel):
    url: str = Field(..., description="URL for the graph store")
    username: str = Field(..., description="Username for the graph store")
    password: str = Field(..., description="Password for the graph store")
    llm: Optional[LLMConfig] = Field(None, description="LLM configuration for querying the graph store")
    custom_prompt: Optional[str] = Field(None, description="Custom prompt to fetch entities from the given text")
    
class GraphStoreConfig(BaseModel):
    provider: str = Field(..., description="Graph store provider name")
    config: GraphProvider

class Mem0Config(BaseModel):
    llm: Optional[LLMProvider] = None
    embedder: Optional[EmbedderProvider] = None
    vector_store: Optional[VectorStoreConfig] = None
    graph_store: Optional[GraphStoreConfig] = None

class ConfigSchema(BaseModel):
    openmemory: Optional[OpenMemoryConfig] = None
    mem0: Mem0Config

def get_default_configuration():
    """Get the default configuration with sensible defaults for LLM and embedder."""
#    return {
#        "openmemory": {
#            "custom_instructions": None
#        },
#        "mem0": {
#            "llm": {
#                "provider": "openai",
#                "config": {
#                    "model": "gpt-4o-mini",
#                    "temperature": 0.1,
#                    "max_tokens": 2000,
#                    "api_key": "env:OPENAI_API_KEY"
#                }
#            },
#            "embedder": {
#                "provider": "openai",
#                "config": {
#                    "model": "text-embedding-3-small",
#                    "api_key": "env:OPENAI_API_KEY"
#                }
#            }
#        }
#    }
    defaultValue =  {
        "mem0": {
            "llm": {
            "provider": "azure_openai",
            "config": {
                "model": "env:LLM_AZURE_DEPLOYMENT",
                "temperature": 0.1,
                "max_tokens": 2000,
                "api_key": "env:LLM_AZURE_OPENAI_API_KEY",
                "api_version": "env:LLM_AZURE_API_VERSION",
                "azure_deployment": "env:LLM_AZURE_DEPLOYMENT",
                "azure_endpoint": "env:LLM_AZURE_ENDPOINT"
            }
            },
            "embedder": {
                "provider": "azure_openai",
                "config": {
                    "model": "env:EMBEDDING_AZURE_DEPLOYMENT",
                    "deployment": "env:EMBEDDING_AZURE_DEPLOYMENT",
                    "endpoint": "env:EMBEDDING_AZURE_ENDPOINT"
                }
            },
            "vector_store": {
                "provider": "pgvector",
                "config": {
                    "host": "env:PGVECTOR_HOST",
                    "port": 8432,                    
                    "collectionName": "env:PGVECTOR_COLLECTION_NAME"
                }
            },
            "graph_store": {
                "provider": "neo4j",
                "config": {
                    "url": "env:NEO4J_URI",
                    "username": "env:NEO4J_USERNAME",
                    "password": "env:NEO4J_PASSWORD"
                }
            }
        },
        "openmemory": {
            "custom_instructions": None,           
        }        
    }    
    pgPort = parseInt(process.env.PGVECTOR_PORT || "-1")
    if (pgPort > 0) {
        defaultValue["mem0"]["vector_store"]["config"]["port"] = pgPort        
    }
    customInstructions = os.getenv("OPENMEMORY_CUSTOM_INSTRUCTIONS")
    if customInstructions:
        defaultValue["openmemory"]["custom_instructions"] = customInstructions
    return defaultValue

def get_config_from_db(db: Session, key: str = "main"):
    """Get configuration from database."""
    config = db.query(ConfigModel).filter(ConfigModel.key == key).first()
    
    if not config:
        # Create default config with proper provider configurations
        default_config = get_default_configuration()
        db_config = ConfigModel(key=key, value=default_config)
        db.add(db_config)
        db.commit()
        db.refresh(db_config)
        return default_config
    
    # Ensure the config has all required sections with defaults
    config_value = config.value
    default_config = get_default_configuration()
    
    # Merge with defaults to ensure all required fields exist
    if "openmemory" not in config_value:
        config_value["openmemory"] = default_config["openmemory"]
    
    if "mem0" not in config_value:
        config_value["mem0"] = default_config["mem0"]
    else:
        # Ensure LLM config exists with defaults
        if "llm" not in config_value["mem0"] or config_value["mem0"]["llm"] is None:
            config_value["mem0"]["llm"] = default_config["mem0"]["llm"]
        
        # Ensure embedder config exists with defaults
        if "embedder" not in config_value["mem0"] or config_value["mem0"]["embedder"] is None:
            config_value["mem0"]["embedder"] = default_config["mem0"]["embedder"]
    
    # Save the updated config back to database if it was modified
    if config_value != config.value:
        config.value = config_value
        db.commit()
        db.refresh(config)
    
    logger.info(f"Configuration loaded from database: {config_value}")

    return config_value

def save_config_to_db(db: Session, config: Dict[str, Any], key: str = "main"):
    """Save configuration to database."""
    db_config = db.query(ConfigModel).filter(ConfigModel.key == key).first()
    
    if db_config:
        db_config.value = config
        db_config.updated_at = None  # Will trigger the onupdate to set current time
    else:
        db_config = ConfigModel(key=key, value=config)
        db.add(db_config)
        
    db.commit()
    db.refresh(db_config)
    return db_config.value

@router.get("/", response_model=ConfigSchema)
async def get_configuration(db: Session = Depends(get_db)):
    """Get the current configuration."""
    config = get_config_from_db(db)
    return config

@router.put("/", response_model=ConfigSchema)
async def update_configuration(config: ConfigSchema, db: Session = Depends(get_db)):
    """Update the configuration."""
    current_config = get_config_from_db(db)
    
    # Convert to dict for processing
    updated_config = current_config.copy()
    
    # Update openmemory settings if provided
    if config.openmemory is not None:
        if "openmemory" not in updated_config:
            updated_config["openmemory"] = {}
        updated_config["openmemory"].update(config.openmemory.dict(exclude_none=True))
    
    # Update mem0 settings
    updated_config["mem0"] = config.mem0.dict(exclude_none=True)
    
    # Save the configuration to database
    save_config_to_db(db, updated_config)
    reset_memory_client()
    return updated_config

@router.post("/reset", response_model=ConfigSchema)
async def reset_configuration(db: Session = Depends(get_db)):
    """Reset the configuration to default values."""
    try:
        # Get the default configuration with proper provider setups
        default_config = get_default_configuration()
        
        # Save it as the current configuration in the database
        save_config_to_db(db, default_config)
        reset_memory_client()
        return default_config
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to reset configuration: {str(e)}"
        )

@router.get("/mem0/llm", response_model=LLMProvider)
async def get_llm_configuration(db: Session = Depends(get_db)):
    """Get only the LLM configuration."""
    config = get_config_from_db(db)
    llm_config = config.get("mem0", {}).get("llm", {})
    return llm_config

@router.put("/mem0/llm", response_model=LLMProvider)
async def update_llm_configuration(llm_config: LLMProvider, db: Session = Depends(get_db)):
    """Update only the LLM configuration."""
    current_config = get_config_from_db(db)
    
    # Ensure mem0 key exists
    if "mem0" not in current_config:
        current_config["mem0"] = {}
    
    # Update the LLM configuration
    current_config["mem0"]["llm"] = llm_config.dict(exclude_none=True)
    
    # Save the configuration to database
    save_config_to_db(db, current_config)
    reset_memory_client()
    return current_config["mem0"]["llm"]

@router.get("/mem0/embedder", response_model=EmbedderProvider)
async def get_embedder_configuration(db: Session = Depends(get_db)):
    """Get only the Embedder configuration."""
    config = get_config_from_db(db)
    embedder_config = config.get("mem0", {}).get("embedder", {})
    return embedder_config

@router.put("/mem0/embedder", response_model=EmbedderProvider)
async def update_embedder_configuration(embedder_config: EmbedderProvider, db: Session = Depends(get_db)):
    """Update only the Embedder configuration."""
    current_config = get_config_from_db(db)
    
    # Ensure mem0 key exists
    if "mem0" not in current_config:
        current_config["mem0"] = {}
    
    # Update the Embedder configuration
    current_config["mem0"]["embedder"] = embedder_config.dict(exclude_none=True)
    
    # Save the configuration to database
    save_config_to_db(db, current_config)
    reset_memory_client()
    return current_config["mem0"]["embedder"]

@router.get("/openmemory", response_model=OpenMemoryConfig)
async def get_openmemory_configuration(db: Session = Depends(get_db)):
    """Get only the OpenMemory configuration."""
    config = get_config_from_db(db)
    openmemory_config = config.get("openmemory", {})
    return openmemory_config

@router.put("/openmemory", response_model=OpenMemoryConfig)
async def update_openmemory_configuration(openmemory_config: OpenMemoryConfig, db: Session = Depends(get_db)):
    """Update only the OpenMemory configuration."""
    current_config = get_config_from_db(db)
    
    # Ensure openmemory key exists
    if "openmemory" not in current_config:
        current_config["openmemory"] = {}
    
    # Update the OpenMemory configuration
    current_config["openmemory"].update(openmemory_config.dict(exclude_none=True))
    
    # Save the configuration to database
    save_config_to_db(db, current_config)
    reset_memory_client()
    return current_config["openmemory"] 