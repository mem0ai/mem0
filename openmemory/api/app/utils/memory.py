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

import hashlib
import json
import os
import socket

from app.database import SessionLocal
from app.models import Config as ConfigModel

from mem0 import Memory

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
    Sets default ollama_base_url if not provided.
    """
    if not config_section or "config" not in config_section:
        return config_section
    
    ollama_config = config_section["config"]
    
    # Set default ollama_base_url if not provided
    if "ollama_base_url" not in ollama_config:
        ollama_config["ollama_base_url"] = "http://host.docker.internal:11434"
    else:
        # Check for ollama_base_url and fix if it's localhost
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


def get_default_memory_config():
    """Get default memory client configuration with sensible defaults."""
    return {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "openmemory",
                "host": "mem0_store",
                "port": 6333
            }
        },
        "llm": {
            "provider": "openai",
            "config": {
                "model": "gpt-4o-mini",
                "temperature": 0.1,
                "max_tokens": 2000,
                "api_key": "env:OPENAI_API_KEY"
            }
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": "text-embedding-3-small",
                "api_key": "env:OPENAI_API_KEY"
            }
        },
        "version": "v1.1"
    }


def _parse_environment_variables(config_dict):
    """
    Parse environment variables in config values.
    Converts 'env:VARIABLE_NAME' to actual environment variable values.
    """
    print(f"🔧 [_parse_environment_variables] Parsing config: {type(config_dict)}")
    
    if isinstance(config_dict, dict):
        parsed_config = {}
        for key, value in config_dict.items():
            print(f"🔧 [_parse_environment_variables] Processing key '{key}' with value: {value}")
            
            if isinstance(value, str) and value.startswith("env:"):
                env_var = value.split(":", 1)[1]
                env_value = os.environ.get(env_var)
                print(f"🔧 [_parse_environment_variables] Looking for env var '{env_var}'")
                
                if env_value:
                    parsed_config[key] = env_value
                    print(f"✅ [_parse_environment_variables] Loaded {env_var} from environment for {key}")
                else:
                    print(f"⚠️ [_parse_environment_variables] Environment variable {env_var} not found, keeping original value")
                    parsed_config[key] = value
            elif isinstance(value, dict):
                print(f"🔧 [_parse_environment_variables] Recursively parsing dict for key '{key}'")
                parsed_config[key] = _parse_environment_variables(value)
            else:
                parsed_config[key] = value
                print(f"🔧 [_parse_environment_variables] Keeping non-env value for key '{key}': {value}")
        
        print(f"🔧 [_parse_environment_variables] Parsed config result: {json.dumps(parsed_config, indent=2)}")
        return parsed_config
    
    print(f"🔧 [_parse_environment_variables] Not a dict, returning as-is: {config_dict}")
    return config_dict


def get_memory_client(custom_instructions: str = None):
    """
    Get or initialize the Mem0 client.

    Args:
        custom_instructions: Optional instructions for the memory project.

    Returns:
        Initialized Mem0 client instance or None if initialization fails.

    Raises:
        Exception: If required API keys are not set or critical configuration is missing.
    """
    global _memory_client, _config_hash

    print("🔍 [get_memory_client] Starting memory client initialization...")
    
    try:
        # Start with default configuration
        print("📋 [get_memory_client] Getting default memory config...")
        config = get_default_memory_config()
        print(f"📋 [get_memory_client] Default config: {json.dumps(config, indent=2)}")
        
        # Variable to track custom instructions
        db_custom_instructions = None
        
        # Load configuration from database
        print("🗄️ [get_memory_client] Loading configuration from database...")
        try:
            db = SessionLocal()
            print("🗄️ [get_memory_client] Database session created")
            
            db_config = db.query(ConfigModel).filter(ConfigModel.key == "main").first()
            print(f"🗄️ [get_memory_client] Database config found: {db_config is not None}")
            
            if db_config:
                json_config = db_config.value
                print(f"🗄️ [get_memory_client] Database config value: {json.dumps(json_config, indent=2)}")
                
                # Extract custom instructions from openmemory settings
                if "openmemory" in json_config and "custom_instructions" in json_config["openmemory"]:
                    db_custom_instructions = json_config["openmemory"]["custom_instructions"]
                    print(f"📝 [get_memory_client] Custom instructions from DB: {db_custom_instructions}")
                
                # Override defaults with configurations from the database
                if "mem0" in json_config:
                    mem0_config = json_config["mem0"]
                    print(f"🔧 [get_memory_client] Mem0 config from DB: {json.dumps(mem0_config, indent=2)}")
                    
                    # Update LLM configuration if available
                    if "llm" in mem0_config and mem0_config["llm"] is not None:
                        print("🔧 [get_memory_client] Updating LLM config from DB...")
                        config["llm"] = mem0_config["llm"]
                        
                        # Fix Ollama URLs for Docker if needed
                        if config["llm"].get("provider") == "ollama":
                            print("🐳 [get_memory_client] Fixing Ollama URLs for Docker...")
                            config["llm"] = _fix_ollama_urls(config["llm"])
                    
                    # Update Embedder configuration if available
                    if "embedder" in mem0_config and mem0_config["embedder"] is not None:
                        print("🔧 [get_memory_client] Updating embedder config from DB...")
                        config["embedder"] = mem0_config["embedder"]
                        
                        # Fix Ollama URLs for Docker if needed
                        if config["embedder"].get("provider") == "ollama":
                            print("🐳 [get_memory_client] Fixing Ollama URLs for Docker...")
                            config["embedder"] = _fix_ollama_urls(config["embedder"])
                else:
                    print("⚠️ [get_memory_client] No mem0 config in database")
            else:
                print("⚠️ [get_memory_client] No configuration found in database, using defaults")
                    
            db.close()
            print("🗄️ [get_memory_client] Database session closed")
                            
        except Exception as e:
            print(f"❌ [get_memory_client] Error loading configuration from database: {e}")
            print("⚠️ [get_memory_client] Using default configuration")
            # Continue with default configuration if database config can't be loaded

        # Use custom_instructions parameter first, then fall back to database value
        instructions_to_use = custom_instructions or db_custom_instructions
        if instructions_to_use:
            print(f"📝 [get_memory_client] Using custom instructions: {instructions_to_use}")
            config["custom_fact_extraction_prompt"] = instructions_to_use
        else:
            print("📝 [get_memory_client] No custom instructions to use")

        # ALWAYS parse environment variables in the final config
        # This ensures that even default config values like "env:OPENAI_API_KEY" get parsed
        print("🔧 [get_memory_client] Parsing environment variables in final config...")
        config = _parse_environment_variables(config)
        print(f"🔧 [get_memory_client] Final config after env parsing: {json.dumps(config, indent=2)}")

        # Check if config has changed by comparing hashes
        current_config_hash = _get_config_hash(config)
        print(f"🔍 [get_memory_client] Current config hash: {current_config_hash}")
        print(f"🔍 [get_memory_client] Previous config hash: {_config_hash}")
        print(f"🔍 [get_memory_client] Memory client exists: {_memory_client is not None}")
        
        # Only reinitialize if config changed or client doesn't exist
        if _memory_client is None or _config_hash != current_config_hash:
            print(f"🚀 [get_memory_client] Initializing memory client with config hash: {current_config_hash}")
            try:
                print("🚀 [get_memory_client] Calling Memory.from_config()...")
                _memory_client = Memory.from_config(config_dict=config)
                _config_hash = current_config_hash
                print("✅ [get_memory_client] Memory client initialized successfully")
                print(f"✅ [get_memory_client] Memory client type: {type(_memory_client)}")
                print(f"✅ [get_memory_client] Memory client attributes: {dir(_memory_client)}")
            except Exception as init_error:
                print(f"❌ [get_memory_client] Failed to initialize memory client: {init_error}")
                print(f"❌ [get_memory_client] Error type: {type(init_error)}")
                print(f"❌ [get_memory_client] Error details: {str(init_error)}")
                import traceback
                print(f"❌ [get_memory_client] Full traceback:")
                traceback.print_exc()
                print("⚠️ [get_memory_client] Server will continue running with limited memory functionality")
                _memory_client = None
                _config_hash = None
                return None
        else:
            print("♻️ [get_memory_client] Using existing memory client (config unchanged)")
        
        print(f"✅ [get_memory_client] Returning memory client: {_memory_client}")
        return _memory_client
        
    except Exception as e:
        print(f"❌ [get_memory_client] Exception occurred while initializing memory client: {e}")
        print(f"❌ [get_memory_client] Error type: {type(e)}")
        import traceback
        print(f"❌ [get_memory_client] Full traceback:")
        traceback.print_exc()
        print("⚠️ [get_memory_client] Server will continue running with limited memory functionality")
        return None


def get_default_user_id():
    return "default_user"
