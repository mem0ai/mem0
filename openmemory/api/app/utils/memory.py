import os
import json

from mem0 import Memory
from app.database import SessionLocal
from app.models import Config as ConfigModel


memory_client = None


def get_memory_client(custom_instructions: str = None):
    """
    Get or initialize the Mem0 client.

    Args:
        custom_instructions: Optional instructions for the memory project.

    Returns:
        Initialized Mem0 client instance.

    Raises:
        Exception: If required API keys are not set.
    """
    global memory_client

    if memory_client is not None:
        return memory_client

    try:
        # Base configuration for vector store
        config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "openmemory",
                    "host": "mem0_store",
                    "port": 6333,
                }
            },
        }
        
        # Load configuration from database
        try:
            db = SessionLocal()
            db_config = db.query(ConfigModel).filter(ConfigModel.key == "main").first()
            
            if db_config:
                json_config = db_config.value
                
                # Add configurations from the database
                if "mem0" in json_config:
                    mem0_config = json_config["mem0"]
                    
                    # Add LLM configuration if available
                    if "llm" in mem0_config:
                        config["llm"] = mem0_config["llm"]
                        
                        # Handle API key - support both direct keys and environment variables
                        if "config" in config["llm"] and "api_key" in config["llm"]["config"]:
                            api_key = config["llm"]["config"]["api_key"]
                            
                            # If API key is set to load from environment
                            if api_key and isinstance(api_key, str) and api_key.startswith("env:"):
                                env_var = api_key.split(":", 1)[1]
                                env_api_key = os.environ.get(env_var)
                                if env_api_key:
                                    config["llm"]["config"]["api_key"] = env_api_key
                                else:
                                    raise Exception(f"{env_var} environment variable not set")
                            # Otherwise, use the API key directly as provided in the config
                    
                    # Add Embedder configuration if available
                    if "embedder" in mem0_config:
                        config["embedder"] = mem0_config["embedder"]
                        
                        # Handle API key - support both direct keys and environment variables
                        if "config" in config["embedder"] and "api_key" in config["embedder"]["config"]:
                            api_key = config["embedder"]["config"]["api_key"]
                            
                            # If API key is set to load from environment
                            if api_key and isinstance(api_key, str) and api_key.startswith("env:"):
                                env_var = api_key.split(":", 1)[1]
                                env_api_key = os.environ.get(env_var)
                                if env_api_key:
                                    config["embedder"]["config"]["api_key"] = env_api_key
                                else:
                                    raise Exception(f"{env_var} environment variable not set")
                            # Otherwise, use the API key directly as provided in the config
            else:
                # If no config in database, try to load from file for backwards compatibility
                try:
                    with open("/usr/src/openmemory/config.json", "r") as f:
                        file_config = json.load(f)
                    
                    # Add configurations from config.json
                    if "mem0" in file_config:
                        mem0_config = file_config["mem0"]
                        
                        # Add LLM configuration if available
                        if "llm" in mem0_config:
                            config["llm"] = mem0_config["llm"]
                            
                            # Handle API key
                            if "config" in config["llm"] and "api_key" in config["llm"]["config"]:
                                api_key = config["llm"]["config"]["api_key"]
                                
                                if api_key and isinstance(api_key, str) and api_key.startswith("env:"):
                                    env_var = api_key.split(":", 1)[1]
                                    env_api_key = os.environ.get(env_var)
                                    if env_api_key:
                                        config["llm"]["config"]["api_key"] = env_api_key
                                    else:
                                        raise Exception(f"{env_var} environment variable not set")
                        
                        # Add Embedder configuration if available
                        if "embedder" in mem0_config:
                            config["embedder"] = mem0_config["embedder"]
                            
                            # Handle API key
                            if "config" in config["embedder"] and "api_key" in config["embedder"]["config"]:
                                api_key = config["embedder"]["config"]["api_key"]
                                
                                if api_key and isinstance(api_key, str) and api_key.startswith("env:"):
                                    env_var = api_key.split(":", 1)[1]
                                    env_api_key = os.environ.get(env_var)
                                    if env_api_key:
                                        config["embedder"]["config"]["api_key"] = env_api_key
                                    else:
                                        raise Exception(f"{env_var} environment variable not set")
                    
                    # Save the file config to database for future use
                    db_config = ConfigModel(key="main", value=file_config)
                    db.add(db_config)
                    db.commit()
                except Exception as e:
                    print(f"Error loading config.json: {e}")
                    # Continue with basic configuration if config.json can't be loaded
                    
            db.close()
                            
        except Exception as e:
            print(f"Error loading configuration: {e}")
            # Continue with basic configuration if database config can't be loaded

        memory_client = Memory.from_config(config_dict=config)
    except Exception as e:
        raise Exception(f"Exception occurred while initializing memory client: {e}")

    # Update project with custom instructions if provided
    if custom_instructions:
        memory_client.update_project(custom_instructions=custom_instructions)

    return memory_client


def get_default_user_id():
    return "default_user"
