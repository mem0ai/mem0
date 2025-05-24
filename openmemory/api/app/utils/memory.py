"""
Memory client utilities for OpenMemory.

This module provides functionality to initialize and manage the Mem0 memory client
with automatic configuration management and Docker environment support.

Docker Ollama Configuration:
When running inside a Docker container and using Ollama as the LLM or embedder provider,
the system automatically detects the Docker environment and adjusts localhost URLs
to properly reach the host machine where Ollama is running.

Supported Docker host resolution (in order of preference):
1. OLLAMA_HOST environment variable (if set)
2. host.docker.internal (Docker Desktop for Mac/Windows)
3. Docker bridge gateway IP (typically 172.17.0.1 on Linux)
4. Fallback to 172.17.0.1

Example configuration that will be automatically adjusted:
{
    "llm": {
        "provider": "ollama",
        "config": {
            "model": "llama3.1:latest",
            "ollama_base_url": "http://localhost:11434"  # Auto-adjusted in Docker
        }
    }
}
"""

import os
import json
import hashlib
import socket
import platform

from mem0 import Memory
from app.database import SessionLocal
from app.models import Config as ConfigModel


_memory_client = None
_config_hash = None


def _get_config_hash(config_dict):
    """Generate a hash of the config to detect changes."""
    config_str = json.dumps(config_dict, sort_keys=True)
    return hashlib.md5(config_str.encode()).hexdigest()


def _get_docker_host_url():
    """
    Determine the appropriate host URL to reach host machine from inside Docker container.
    Returns the best available option for reaching the host from inside a container.
    """
    # Check for custom environment variable first
    custom_host = os.environ.get('OLLAMA_HOST')
    if custom_host:
        print(f"Using custom Ollama host from OLLAMA_HOST: {custom_host}")
        return custom_host.replace('http://', '').replace('https://', '').split(':')[0]
    
    # Check if we're running inside Docker
    if not os.path.exists('/.dockerenv'):
        # Not in Docker, return localhost as-is
        return "localhost"
    
    print("Detected Docker environment, adjusting host URL for Ollama...")
    
    # Try different host resolution strategies
    host_candidates = []
    
    # 1. host.docker.internal (works on Docker Desktop for Mac/Windows)
    try:
        socket.gethostbyname('host.docker.internal')
        host_candidates.append('host.docker.internal')
        print("Found host.docker.internal")
    except socket.gaierror:
        pass
    
    # 2. Docker bridge gateway (typically 172.17.0.1 on Linux)
    try:
        with open('/proc/net/route', 'r') as f:
            for line in f:
                fields = line.strip().split()
                if fields[1] == '00000000':  # Default route
                    gateway_hex = fields[2]
                    gateway_ip = socket.inet_ntoa(bytes.fromhex(gateway_hex)[::-1])
                    host_candidates.append(gateway_ip)
                    print(f"Found Docker gateway: {gateway_ip}")
                    break
    except (FileNotFoundError, IndexError, ValueError):
        pass
    
    # 3. Fallback to common Docker bridge IP
    if not host_candidates:
        host_candidates.append('172.17.0.1')
        print("Using fallback Docker bridge IP: 172.17.0.1")
    
    # Return the first available candidate
    return host_candidates[0]


def _fix_ollama_urls(config_section):
    """
    Fix Ollama URLs for Docker environment.
    Replaces localhost URLs with appropriate Docker host URLs.
    """
    if not config_section or "config" not in config_section:
        return config_section
    
    ollama_config = config_section["config"]
    
    # Check for ollama_base_url and fix if it's localhost
    if "ollama_base_url" in ollama_config:
        url = ollama_config["ollama_base_url"]
        if "localhost" in url or "127.0.0.1" in url:
            docker_host = _get_docker_host_url()
            if docker_host != "localhost":
                new_url = url.replace("localhost", docker_host).replace("127.0.0.1", docker_host)
                ollama_config["ollama_base_url"] = new_url
                print(f"Adjusted Ollama URL from {url} to {new_url}")
    
    return config_section


def reset_memory_client():
    """Reset the global memory client to force reinitialization with new config."""
    global _memory_client, _config_hash
    _memory_client = None
    _config_hash = None


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
    global _memory_client, _config_hash

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
                        
                        # Fix Ollama URLs for Docker if needed
                        if config["llm"].get("provider") == "ollama":
                            config["llm"] = _fix_ollama_urls(config["llm"])
                        
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
                        
                        # Fix Ollama URLs for Docker if needed
                        if config["embedder"].get("provider") == "ollama":
                            config["embedder"] = _fix_ollama_urls(config["embedder"])
                        
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
                            
                            # Fix Ollama URLs for Docker if needed
                            if config["llm"].get("provider") == "ollama":
                                config["llm"] = _fix_ollama_urls(config["llm"])
                            
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
                            
                            # Fix Ollama URLs for Docker if needed
                            if config["embedder"].get("provider") == "ollama":
                                config["embedder"] = _fix_ollama_urls(config["embedder"])
                            
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

        # Check if config has changed by comparing hashes
        current_config_hash = _get_config_hash(config)
        
        # Only reinitialize if config changed or client doesn't exist
        if _memory_client is None or _config_hash != current_config_hash:
            print(f"Initializing memory client with config hash: {current_config_hash}")
            _memory_client = Memory.from_config(config_dict=config)
            _config_hash = current_config_hash
            
            # Update project with custom instructions if provided
            if custom_instructions:
                _memory_client.update_project(custom_instructions=custom_instructions)
        
        return _memory_client
        
    except Exception as e:
        raise Exception(f"Exception occurred while initializing memory client: {e}")


def get_default_user_id():
    return "default_user"
