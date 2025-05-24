import os
import json
import shutil
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Config as ConfigModel
from app.utils.memory import reset_memory_client

router = APIRouter(prefix="/api/v1/config", tags=["config"])

# We'll still keep paths for backward compatibility or initial setup
CONFIG_PATH = "/usr/src/openmemory/config.json"
DEFAULT_CONFIG_PATH = "/usr/src/openmemory/default_config.json"

class LLMConfig(BaseModel):
    model: str = Field(..., description="LLM model name")
    temperature: float = Field(..., description="Temperature setting for the model")
    max_tokens: int = Field(..., description="Maximum tokens to generate")
    api_key: Optional[str] = Field(None, description="API key or 'env:API_KEY' to use environment variable")

class LLMProvider(BaseModel):
    provider: str = Field(..., description="LLM provider name")
    config: LLMConfig

class EmbedderConfig(BaseModel):
    model: str = Field(..., description="Embedder model name")
    api_key: Optional[str] = Field(None, description="API key or 'env:API_KEY' to use environment variable")

class EmbedderProvider(BaseModel):
    provider: str = Field(..., description="Embedder provider name")
    config: EmbedderConfig

class Mem0Config(BaseModel):
    llm: Optional[LLMProvider] = None
    embedder: Optional[EmbedderProvider] = None

class ConfigSchema(BaseModel):
    mem0: Mem0Config

def get_default_config():
    """Read the default configuration file."""
    try:
        if not os.path.exists(DEFAULT_CONFIG_PATH):
            raise HTTPException(
                status_code=404, 
                detail="Default configuration file not found"
            )
            
        with open(DEFAULT_CONFIG_PATH, "r") as f:
            config = json.load(f)
            
        return config
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500, 
            detail="Invalid JSON in default configuration file"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error reading default configuration: {str(e)}"
        )

def get_config_from_db(db: Session, key: str = "main"):
    """Get configuration from database."""
    config = db.query(ConfigModel).filter(ConfigModel.key == key).first()
    
    if not config:
        # If config doesn't exist in DB, try to load from file
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r") as f:
                    file_config = json.load(f)
                
                # Handle legacy format (no mem0 parent key)
                if "mem0" not in file_config and "llm" in file_config:
                    file_config = {"mem0": {"llm": file_config["llm"]}}
                
                # Save to database
                db_config = ConfigModel(key=key, value=file_config)
                db.add(db_config)
                db.commit()
                db.refresh(db_config)
                return file_config
            except Exception:
                # If file loading fails, try default config
                if os.path.exists(DEFAULT_CONFIG_PATH):
                    try:
                        default_config = get_default_config()
                        db_config = ConfigModel(key=key, value=default_config)
                        db.add(db_config)
                        db.commit()
                        db.refresh(db_config)
                        return default_config
                    except Exception:
                        pass
                
                # Create empty config if nothing else works
                empty_config = {"mem0": {"llm": None, "embedder": None}}
                db_config = ConfigModel(key=key, value=empty_config)
                db.add(db_config)
                db.commit()
                db.refresh(db_config)
                return empty_config
        else:
            # Try default config
            if os.path.exists(DEFAULT_CONFIG_PATH):
                try:
                    default_config = get_default_config()
                    db_config = ConfigModel(key=key, value=default_config)
                    db.add(db_config)
                    db.commit()
                    db.refresh(db_config)
                    return default_config
                except Exception:
                    pass
            
            # Create empty config if nothing else works
            empty_config = {"mem0": {"llm": None, "embedder": None}}
            db_config = ConfigModel(key=key, value=empty_config)
            db.add(db_config)
            db.commit()
            db.refresh(db_config)
            return empty_config
    
    return config.value

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
    updated_config["mem0"] = config.mem0.dict(exclude_none=True)
    
    # Save the configuration to database
    save_config_to_db(db, updated_config)
    reset_memory_client()
    return updated_config

@router.post("/reset", response_model=ConfigSchema)
async def reset_configuration(db: Session = Depends(get_db)):
    """Reset the configuration to default values."""
    try:
        # Get the default configuration
        default_config = get_default_config()
        
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