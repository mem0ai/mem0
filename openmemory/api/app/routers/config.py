from typing import Any, Dict, Optional

from app.database import get_db
from app.models import Config as ConfigModel
from app.utils.memory import reset_memory_client
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
# Import mem0 config classes for reference, but we'll create Pydantic models that match their structure

router = APIRouter(prefix="/api/v1/config", tags=["config"])

# Pydantic models that match mem0's config structure exactly
class LLMConfig(BaseModel):
    """Matches mem0.configs.llms.openai.OpenAIConfig structure"""
    model: Optional[str] = Field(None, description="LLM model name")
    temperature: float = Field(0.1, description="Temperature for LLM responses")
    api_key: Optional[str] = Field(None, description="API key for LLM provider")
    max_tokens: int = Field(2000, description="Maximum tokens for LLM responses")
    openai_base_url: Optional[str] = Field(None, description="Base URL for OpenAI-compatible API")

class LLMProvider(BaseModel):
    provider: str = Field(..., description="LLM provider name")
    config: LLMConfig

class EmbedderConfig(BaseModel):
    """Matches mem0.configs.embeddings.base.BaseEmbedderConfig structure"""
    model: Optional[str] = Field(None, description="Embedder model name")
    api_key: Optional[str] = Field(None, description="API key for embedder provider")
    openai_base_url: Optional[str] = Field(None, description="Base URL for OpenAI-compatible API")
    embedding_dims: Optional[int] = Field(1536, description="Dimensions of the embedding model")

class EmbedderProvider(BaseModel):
    provider: str = Field(..., description="Embedder provider name")
    config: EmbedderConfig

class VectorStoreProvider(BaseModel):
    provider: str = Field(..., description="Vector store provider name")
    # Below config can vary widely based on the vector store used. Refer https://docs.mem0.ai/components/vectordbs/config
    config: Dict[str, Any] = Field(..., description="Vector store-specific configuration")

class GraphStoreConfig(BaseModel):
    """Matches mem0.graphs.configs.GraphStoreConfig structure"""
    provider: str = Field("neo4j", description="Provider of the data store")
    config: Optional[Dict[str, Any]] = Field(None, description="Configuration for the specific data store")
    llm: Optional[LLMProvider] = Field(None, description="LLM configuration for querying the graph store")
    custom_prompt: Optional[str] = Field(None, description="Custom prompt to fetch entities from the given text")

class OpenMemoryConfig(BaseModel):
    custom_instructions: Optional[str] = Field(None, description="Custom instructions for memory management and fact extraction")

class Mem0Config(BaseModel):
    llm: Optional[LLMProvider] = None
    embedder: Optional[EmbedderProvider] = None
    vector_store: Optional[VectorStoreProvider] = None
    graph_store: Optional[GraphStoreConfig] = None

class ConfigSchema(BaseModel):
    openmemory: Optional[OpenMemoryConfig] = None
    mem0: Optional[Mem0Config] = None

def get_default_configuration():
    """Get the default configuration with sensible defaults for LLM, embedder, vector store, and graph store."""
    return {
        "openmemory": {
            "custom_instructions": None
        },
        "mem0": {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "gpt-4o-mini",
                    "temperature": 0.1,
                    "max_tokens": 2000,
                    "api_key": "env:OPENAI_API_KEY",
                    "openai_base_url": "env:OPENAI_BASE_URL"
                }
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small",
                    "api_key": "env:OPENAI_API_KEY",
                    "openai_base_url": "env:OPENAI_BASE_URL"
                }
            },
            "vector_store": None,
            "graph_store": None  # Optional - only configured if Neo4j env vars are set
        }
    }

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
        
        # Ensure vector_store config exists with defaults
        if "vector_store" not in config_value["mem0"] or config_value["mem0"]["vector_store"] is None:
            config_value["mem0"]["vector_store"] = default_config["mem0"]["vector_store"]
        
        # Graph store is optional - only set defaults if user explicitly configures it
        # If not present, it remains None (disabled)
    
    # Save the updated config back to database if it was modified
    if config_value != config.value:
        config.value = config_value
        db.commit()
        db.refresh(config)
    
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

    # Save to database
    save_config_to_db(db, updated_config)

    # Reset memory client to pick up new configuration
    reset_memory_client()

    return updated_config


@router.patch("/", response_model=ConfigSchema)
async def patch_configuration(config_update: ConfigSchema, db: Session = Depends(get_db)):
    """Update parts of the configuration."""
    current_config = get_config_from_db(db)

    def deep_update(source, overrides):
        for key, value in overrides.items():
            if isinstance(value, dict) and key in source and isinstance(source[key], dict):
                source[key] = deep_update(source[key], value)
            else:
                source[key] = value
        return source

    update_data = config_update.dict(exclude_unset=True)
    updated_config = deep_update(current_config, update_data)

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

@router.get("/mem0/vector_store", response_model=Optional[VectorStoreProvider])
async def get_vector_store_configuration(db: Session = Depends(get_db)):
    """Get only the Vector Store configuration."""
    config = get_config_from_db(db)
    vector_store_config = config.get("mem0", {}).get("vector_store", None)
    return vector_store_config

@router.put("/mem0/vector_store", response_model=VectorStoreProvider)
async def update_vector_store_configuration(vector_store_config: VectorStoreProvider, db: Session = Depends(get_db)):
    """Update only the Vector Store configuration."""
    current_config = get_config_from_db(db)
    
    # Ensure mem0 key exists
    if "mem0" not in current_config:
        current_config["mem0"] = {}
    
    # Update the Vector Store configuration
    current_config["mem0"]["vector_store"] = vector_store_config.dict(exclude_none=True)
    
    # Save the configuration to database
    save_config_to_db(db, current_config)
    reset_memory_client()
    return current_config["mem0"]["vector_store"]

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
