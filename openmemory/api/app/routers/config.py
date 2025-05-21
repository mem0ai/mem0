import os
import json
import shutil
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/config", tags=["config"])

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

class ConfigModel(BaseModel):
    mem0: Mem0Config

def get_config():
    """Read the configuration file."""
    try:
        if not os.path.exists(CONFIG_PATH):
            # If config doesn't exist, copy the default config if available
            if os.path.exists(DEFAULT_CONFIG_PATH):
                shutil.copy(DEFAULT_CONFIG_PATH, CONFIG_PATH)
            else:
                raise HTTPException(
                    status_code=404, 
                    detail="Configuration file not found and no default config available"
                )
            
        with open(CONFIG_PATH, "r") as f:
            config = json.load(f)
            
        # Handle legacy format (no mem0 parent key)
        if "mem0" not in config and "llm" in config:
            config = {"mem0": {"llm": config["llm"]}}
            
        return config
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500, 
            detail="Invalid JSON in configuration file"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error reading configuration: {str(e)}"
        )

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

def save_config(config: Dict[str, Any]):
    """Write the configuration file."""
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error writing configuration: {str(e)}"
        )

def mask_api_keys(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a copy of the config with API keys masked for display.
    This is useful when sending to the frontend.
    """
    config_copy = config_dict.copy()
    
    if "mem0" in config_copy:
        if "llm" in config_copy["mem0"] and "config" in config_copy["mem0"]["llm"]:
            llm_config = config_copy["mem0"]["llm"]["config"]
            if "api_key" in llm_config and llm_config["api_key"] and not llm_config["api_key"].startswith("env:"):
                # Mask API key for display purposes
                llm_config["api_key"] = "********"
                
        if "embedder" in config_copy["mem0"] and "config" in config_copy["mem0"]["embedder"]:
            embedder_config = config_copy["mem0"]["embedder"]["config"]
            if "api_key" in embedder_config and embedder_config["api_key"] and not embedder_config["api_key"].startswith("env:"):
                # Mask API key for display purposes
                embedder_config["api_key"] = "********"
    
    return config_copy

@router.get("/", response_model=ConfigModel)
async def get_configuration():
    """Get the current configuration."""
    config = get_config()
    
    # For security, mask direct API keys when returning to frontend
    safe_config = mask_api_keys(config)
    return safe_config

@router.put("/", response_model=ConfigModel)
async def update_configuration(config: ConfigModel):
    """Update the configuration."""
    current_config = get_config()
    
    # Convert to dict for processing
    updated_config = current_config.copy()
    updated_config["mem0"] = config.mem0.dict(exclude_none=True)
    
    # Save the configuration as provided (including API keys if directly set)
    save_config(updated_config)
    
    # For security, return masked API keys
    safe_config = mask_api_keys(updated_config)
    return safe_config

@router.post("/reset", response_model=ConfigModel)
async def reset_configuration():
    """Reset the configuration to default values."""
    try:
        # Get the default configuration
        default_config = get_default_config()
        
        # Save it as the current configuration
        save_config(default_config)
        
        # For security, mask direct API keys when returning
        safe_config = mask_api_keys(default_config)
        return safe_config
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to reset configuration: {str(e)}"
        )

@router.get("/mem0/llm", response_model=LLMProvider)
async def get_llm_configuration():
    """Get only the LLM configuration."""
    config = get_config()
    llm_config = config.get("mem0", {}).get("llm", {})
    
    # Mask API key if present
    if "config" in llm_config and "api_key" in llm_config["config"] and llm_config["config"]["api_key"] and not llm_config["config"]["api_key"].startswith("env:"):
        llm_config["config"]["api_key"] = "********"
        
    return llm_config

@router.put("/mem0/llm", response_model=LLMProvider)
async def update_llm_configuration(llm_config: LLMProvider):
    """Update only the LLM configuration."""
    current_config = get_config()
    
    # Ensure mem0 key exists
    if "mem0" not in current_config:
        current_config["mem0"] = {}
    
    # Update the LLM configuration
    current_config["mem0"]["llm"] = llm_config.dict(exclude_none=True)
    
    # Save the configuration with API key if provided
    save_config(current_config)
    
    # Create masked version for response
    response_config = current_config.copy()
    if "config" in response_config["mem0"]["llm"] and "api_key" in response_config["mem0"]["llm"]["config"] and response_config["mem0"]["llm"]["config"]["api_key"] and not response_config["mem0"]["llm"]["config"]["api_key"].startswith("env:"):
        response_config["mem0"]["llm"]["config"]["api_key"] = "********"
        
    return response_config["mem0"]["llm"]

@router.get("/mem0/embedder", response_model=EmbedderProvider)
async def get_embedder_configuration():
    """Get only the Embedder configuration."""
    config = get_config()
    embedder_config = config.get("mem0", {}).get("embedder", {})
    
    # Mask API key if present
    if "config" in embedder_config and "api_key" in embedder_config["config"] and embedder_config["config"]["api_key"] and not embedder_config["config"]["api_key"].startswith("env:"):
        embedder_config["config"]["api_key"] = "********"
        
    return embedder_config

@router.put("/mem0/embedder", response_model=EmbedderProvider)
async def update_embedder_configuration(embedder_config: EmbedderProvider):
    """Update only the Embedder configuration."""
    current_config = get_config()
    
    # Ensure mem0 key exists
    if "mem0" not in current_config:
        current_config["mem0"] = {}
    
    # Update the Embedder configuration
    current_config["mem0"]["embedder"] = embedder_config.dict(exclude_none=True)
    
    # Save the configuration with API key if provided
    save_config(current_config)
    
    # Create masked version for response
    response_config = current_config.copy()
    if "config" in response_config["mem0"]["embedder"] and "api_key" in response_config["mem0"]["embedder"]["config"] and response_config["mem0"]["embedder"]["config"]["api_key"] and not response_config["mem0"]["embedder"]["config"]["api_key"].startswith("env:"):
        response_config["mem0"]["embedder"]["config"]["api_key"] = "********"
        
    return response_config["mem0"]["embedder"] 