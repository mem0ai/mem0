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
import logging

from app.database import SessionLocal
from app.models import Config as ConfigModel, Prompt, PromptType

from mem0 import Memory, AsyncMemory

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


def get_prompts_from_db(db: SessionLocal):
    """Load active prompts from the database."""
    prompts = {}
    try:
        # Load all active prompts
        db_prompts = db.query(Prompt).filter(Prompt.is_active == True).all()

        for prompt in db_prompts:
            # prompt_type is already a string in the database, not an enum
            prompts[prompt.prompt_type] = prompt.content

        logging.info(f"Loaded {len(prompts)} active prompts from database")
    except Exception as e:
        logging.warning(f"Failed to load prompts from database: {e}")

    return prompts


def get_default_memory_config():
    """Get default memory client configuration with sensible defaults."""
    # Detect vector store based on environment variables
    vector_store_config = {
        "collection_name": "openmemory",
        "host": "mem0_store",
    }
    
    # Check for different vector store configurations based on environment variables
    if os.environ.get('CHROMA_HOST') and os.environ.get('CHROMA_PORT'):
        vector_store_provider = "chroma"
        vector_store_config.update({
            "host": os.environ.get('CHROMA_HOST'),
            "port": int(os.environ.get('CHROMA_PORT'))
        })
    elif os.environ.get('QDRANT_HOST') and os.environ.get('QDRANT_PORT'):
        vector_store_provider = "qdrant"
        vector_store_config.update({
            "host": os.environ.get('QDRANT_HOST'),
            "port": int(os.environ.get('QDRANT_PORT'))
        })
    elif os.environ.get('WEAVIATE_CLUSTER_URL') or (os.environ.get('WEAVIATE_HOST') and os.environ.get('WEAVIATE_PORT')):
        vector_store_provider = "weaviate"
        # Prefer an explicit cluster URL if provided; otherwise build from host/port
        cluster_url = os.environ.get('WEAVIATE_CLUSTER_URL')
        if not cluster_url:
            weaviate_host = os.environ.get('WEAVIATE_HOST')
            weaviate_port = int(os.environ.get('WEAVIATE_PORT'))
            cluster_url = f"http://{weaviate_host}:{weaviate_port}"
        vector_store_config = {
            "collection_name": "openmemory",
            "cluster_url": cluster_url
        }
    elif os.environ.get('REDIS_URL'):
        vector_store_provider = "redis"
        vector_store_config = {
            "collection_name": "openmemory",
            "redis_url": os.environ.get('REDIS_URL')
        }
    elif os.environ.get('PG_HOST') and os.environ.get('PG_PORT'):
        vector_store_provider = "pgvector"
        vector_store_config.update({
            "host": os.environ.get('PG_HOST'),
            "port": int(os.environ.get('PG_PORT')),
            "dbname": os.environ.get('PG_DB', 'mem0'),
            "user": os.environ.get('PG_USER', 'mem0'),
            "password": os.environ.get('PG_PASSWORD', 'mem0')
        })
    elif os.environ.get('MILVUS_HOST') and os.environ.get('MILVUS_PORT'):
        vector_store_provider = "milvus"
        # Construct the full URL as expected by MilvusDBConfig
        milvus_host = os.environ.get('MILVUS_HOST')
        milvus_port = int(os.environ.get('MILVUS_PORT'))
        milvus_url = f"http://{milvus_host}:{milvus_port}"
        
        vector_store_config = {
            "collection_name": "openmemory",
            "url": milvus_url,
            "token": os.environ.get('MILVUS_TOKEN', ''),  # Always include, empty string for local setup
            "db_name": os.environ.get('MILVUS_DB_NAME', ''),
            "embedding_model_dims": 1536,
            "metric_type": "COSINE"  # Using COSINE for better semantic similarity
        }
    elif os.environ.get('ELASTICSEARCH_HOST') and os.environ.get('ELASTICSEARCH_PORT'):
        vector_store_provider = "elasticsearch"
        # Construct the full URL with scheme since Elasticsearch client expects it
        elasticsearch_host = os.environ.get('ELASTICSEARCH_HOST')
        elasticsearch_port = int(os.environ.get('ELASTICSEARCH_PORT'))
        # Use http:// scheme since we're not using SSL
        full_host = f"http://{elasticsearch_host}"
        
        vector_store_config.update({
            "host": full_host,
            "port": elasticsearch_port,
            "user": os.environ.get('ELASTICSEARCH_USER', 'elastic'),
            "password": os.environ.get('ELASTICSEARCH_PASSWORD', 'changeme'),
            "verify_certs": False,
            "use_ssl": False,
            "embedding_model_dims": 1536
        })
    elif os.environ.get('OPENSEARCH_HOST') and os.environ.get('OPENSEARCH_PORT'):
        vector_store_provider = "opensearch"
        vector_store_config.update({
            "host": os.environ.get('OPENSEARCH_HOST'),
            "port": int(os.environ.get('OPENSEARCH_PORT'))
        })
    elif os.environ.get('FAISS_PATH'):
        vector_store_provider = "faiss"
        vector_store_config = {
            "collection_name": "openmemory",
            "path": os.environ.get('FAISS_PATH'),
            "embedding_model_dims": 1536,
            "distance_strategy": "cosine"
        }
    else:
        # Default fallback to Qdrant
        vector_store_provider = "qdrant"
        vector_store_config.update({
            "port": 6333,
        })
    
    # Build the complete configuration structure
    config = {
        "vector_store": {
            "provider": vector_store_provider,
            "config": vector_store_config
        },
        "llm": {
            "provider": "openai",
            "config": {
                "model": "gpt-4o-mini",
                "api_key": os.environ.get('OPENAI_API_KEY'),
                "temperature": 0.1,
                "max_tokens": 2000,
            }
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": "text-embedding-3-small",
                "api_key": os.environ.get('OPENAI_API_KEY'),
            }
        }
    }
    
    # Only add graph store if Neo4j environment variables are configured
    if os.environ.get('NEO4J_URL') or os.environ.get('NEO4J_USERNAME') or os.environ.get('NEO4J_PASSWORD'):
        config["graph_store"] = {
            "provider": "neo4j",
            "config": {
                "url": os.environ.get('NEO4J_URL', 'neo4j://neo4j'),
                "username": os.environ.get('NEO4J_USERNAME', 'neo4j'),
                "password": os.environ.get('NEO4J_PASSWORD'),
                "database": os.environ.get('NEO4J_DB', 'neo4j'),
            },
            "llm": None,
            "custom_prompt": None
        }
    else:
        # Set graph_store to None to indicate it's not configured
        config["graph_store"] = None
    
    # Adjust base URL for Docker if needed
    base_url = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    if base_url.startswith('http://localhost'):
        base_url = _get_docker_host_url(base_url)
    
    # Only add base_url if it's not the default
    if base_url != 'https://api.openai.com/v1':
        config["llm"]["config"]["openai_base_url"] = base_url
        config["embedder"]["config"]["openai_base_url"] = base_url
    
    return config


def _parse_environment_variables(config_dict):
    """
    Parse environment variables in config values.
    Converts 'env:VARIABLE_NAME' to actual environment variable values.
    """
    if isinstance(config_dict, dict):
        parsed_config = {}
        for key, value in config_dict.items():
            if isinstance(value, str) and value.startswith("env:"):
                env_var = value.split(":", 1)[1]
                env_value = os.environ.get(env_var)
                if env_value:
                    parsed_config[key] = env_value
                    print(f"Loaded {env_var} from environment for {key}")
                else:
                    print(f"Warning: Environment variable {env_var} not found, keeping original value")
                    parsed_config[key] = value
            elif isinstance(value, dict):
                parsed_config[key] = _parse_environment_variables(value)
            else:
                parsed_config[key] = value
        return parsed_config
    return config_dict


async def get_memory_client(custom_instructions: str = None):
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

    try:
        # Start with default configuration
        config = get_default_memory_config()
        
        # Variable to track custom instructions
        db_custom_instructions = None
        db_prompts = {}

        # Load configuration from database
        try:
            db = SessionLocal()

            # Load prompts from database
            db_prompts = get_prompts_from_db(db)

            db_config = db.query(ConfigModel).filter(ConfigModel.key == "main").first()
            
            if db_config:
                json_config = db_config.value
                
                # Extract custom instructions from openmemory settings
                if "openmemory" in json_config and "custom_instructions" in json_config["openmemory"]:
                    db_custom_instructions = json_config["openmemory"]["custom_instructions"]
                
                # Override defaults with configurations from the database
                if "mem0" in json_config:
                    mem0_config = json_config["mem0"]
                    
                    # Update LLM configuration if available
                    if "llm" in mem0_config and mem0_config["llm"] is not None:
                        config["llm"] = mem0_config["llm"]
                        
                        # Fix Ollama URLs for Docker if needed
                        if config["llm"].get("provider") == "ollama":
                            config["llm"] = _fix_ollama_urls(config["llm"])
                    
                    # Update Embedder configuration if available
                    if "embedder" in mem0_config and mem0_config["embedder"] is not None:
                        config["embedder"] = mem0_config["embedder"]
                        
                        # Fix Ollama URLs for Docker if needed
                        if config["embedder"].get("provider") == "ollama":
                            config["embedder"] = _fix_ollama_urls(config["embedder"])

                    if "vector_store" in mem0_config and mem0_config["vector_store"] is not None:
                        config["vector_store"] = mem0_config["vector_store"]
                    
                    # Update Graph Store configuration if available
                    if "graph_store" in mem0_config and mem0_config["graph_store"] is not None:
                        config["graph_store"] = mem0_config["graph_store"]
            else:
                print("No configuration found in database, using defaults")
                    
            db.close()
                            
        except Exception as e:
            print(f"Warning: Error loading configuration from database: {e}")
            print("Using default configuration")
            # Continue with default configuration if database config can't be loaded

        # Use custom_instructions parameter first, then fall back to database value
        instructions_to_use = custom_instructions or db_custom_instructions
        if instructions_to_use:
            config["custom_fact_extraction_prompt"] = instructions_to_use

        # Inject prompts from database if available and no custom_instructions
        # Prioritize: custom_instructions parameter > db prompts > default prompts
        if not instructions_to_use and db_prompts:
            # Use user_memory_extraction prompt if available
            if "user_memory_extraction" in db_prompts:
                config["custom_fact_extraction_prompt"] = db_prompts["user_memory_extraction"]
                logging.info("Using user_memory_extraction prompt from database")

            # Use update_memory prompt if available
            if "update_memory" in db_prompts:
                config["custom_update_memory_prompt"] = db_prompts["update_memory"]
                logging.info("Using update_memory prompt from database")

        # ALWAYS parse environment variables in the final config
        # This ensures that even default config values like "env:OPENAI_API_KEY" get parsed
        print("Parsing environment variables in final config...")
        config = _parse_environment_variables(config)

        # Check if config has changed by comparing hashes
        current_config_hash = _get_config_hash(config)
        
        # Only reinitialize if config changed or client doesn't exist
        if _memory_client is None or _config_hash != current_config_hash:
            print(f"Initializing memory client with config hash: {current_config_hash}")
            try:
                print("Initializing ASYNC memory client")
                _memory_client = await AsyncMemory.from_config(config_dict=config)          
                _config_hash = current_config_hash
                print("Memory client initialized successfully")
            except Exception as init_error:
                print(f"Warning: Failed to initialize memory client: {init_error}")
                print("Server will continue running with limited memory functionality")
                _memory_client = None
                _config_hash = None
                return None
        
        return _memory_client
        
    except Exception as e:
        print(f"Warning: Exception occurred while initializing memory client: {e}")
        print("Server will continue running with limited memory functionality")
        return None


def get_default_user_id():
    return "default_user"


async def create_memory_async(
    text: str,
    user_id: str,
    app_name: str,
    metadata: dict = None,
    memory_client=None
):
    """
    Shared async memory creation function used by both main API and MCP server.
    
    Args:
        text: The memory text content
        user_id: The user ID
        app_name: The app name
        metadata: Optional metadata dict
        memory_client: Optional pre-initialized memory client
    
    Returns:
        tuple: (placeholder_memory, background_task)
    """
    import asyncio
    import time
    import uuid
    from app.models import App, Memory, MemoryState, MemoryStatusHistory, User
    from app.utils.db import get_user_and_app
    
    if metadata is None:
        metadata = {}
    
    # Get memory client if not provided
    if memory_client is None:
        memory_client = await get_memory_client()
        if not memory_client:
            raise Exception("Memory client is not available")
    
    # Create database session
    db = SessionLocal()
    try:
        # Get or create user and app
        user, app = get_user_and_app(db, user_id=user_id, app_id=app_name)
        
        # Check if app is active
        if not app.is_active:
            raise Exception(f"App {app.name} is currently paused on OpenMemory. Cannot create new memories.")
        
        # Create a placeholder memory record immediately
        placeholder_memory = Memory(
            user_id=user.id,
            app_id=app.id,
            content=text,
            metadata_=metadata,
            state=MemoryState.processing  # Mark as processing
        )
        db.add(placeholder_memory)
        db.commit()
        db.refresh(placeholder_memory)
        
        # Start memory creation in background (non-blocking)
        async def create_memory_background():
            """Background task to create memory without blocking the response"""
            # Create a new database session for the background task
            db_session = SessionLocal()
            
            try:
                start_time = time.time()
                qdrant_response = await memory_client.add(
                    text,
                    user_id=user_id,
                    metadata={
                        "source_app": "openmemory",
                        "mcp_client": app_name,
                    }
                )
            
                # Log timing information
                total_duration = time.time() - start_time
                logging.info(f"Background memory creation timing - Total: {total_duration:.3f}s")
                
                # Log the response for debugging
                logging.info(f"Background Qdrant response: {qdrant_response}")
                
                # Get fresh user and app objects from the new session
                user_obj = db_session.query(User).filter(User.user_id == user_id).first()
                app_obj = db_session.query(App).filter(App.name == app_name).first()
                
                # Get the placeholder memory from the new session using its ID
                placeholder_memory_background = db_session.query(Memory).filter(Memory.id == placeholder_memory.id).first()
                if not placeholder_memory_background:
                    logging.error(f"Placeholder memory {placeholder_memory.id} not found in background session")
                    return
                
                # Process Qdrant response and update database
                if 'results' in qdrant_response and qdrant_response['results']:
                    for idx, result in enumerate(qdrant_response['results']):
                        if result['event'] == 'ADD':
                            # Get the Qdrant-generated ID
                            memory_id = uuid.UUID(result['id'])

                            if idx == 0:
                                # Update the placeholder memory with the first result
                                placeholder_memory_background.id = memory_id
                                placeholder_memory_background.content = result['memory']
                                placeholder_memory_background.state = MemoryState.active
                                memory_obj = placeholder_memory_background
                            else:
                                # Create NEW memory records for additional facts
                                memory_obj = Memory(
                                    id=memory_id,
                                    user_id=user_obj.id,
                                    app_id=app_obj.id,
                                    content=result['memory'],
                                    metadata_=metadata,
                                    state=MemoryState.active
                                )
                                db_session.add(memory_obj)

                            # Create history entry
                            history = MemoryStatusHistory(
                                memory_id=memory_id,
                                changed_by=user_obj.id,
                                old_state=MemoryState.processing,
                                new_state=MemoryState.active
                            )
                            db_session.add(history)

                            db_session.commit()
                            db_session.refresh(memory_obj)
                            logging.info(f"Background memory created/updated: {memory_id}")
                
                # If no results, mark as deleted (relations are stored in graph store separately)
                else:
                    placeholder_memory_background.state = MemoryState.deleted
                    
                    # Create history entry
                    history = MemoryStatusHistory(
                        memory_id=placeholder_memory_background.id,
                        changed_by=user_obj.id,
                        old_state=MemoryState.processing,
                        new_state=MemoryState.deleted
                    )
                    db_session.add(history)
                    
                    db_session.commit()
                    db_session.refresh(placeholder_memory_background)
                    logging.info(f"Background memory completed (no facts extracted, marked as deleted): {placeholder_memory_background.id}")
                    
            except Exception as e:
                logging.error(f"Background memory creation failed: {e}")
                # Mark the memory as deleted on error
                try:
                    placeholder_memory_background = db_session.query(Memory).filter(Memory.id == placeholder_memory.id).first()
                    if placeholder_memory_background:
                        placeholder_memory_background.state = MemoryState.deleted
                        placeholder_memory_background.content = f"Error: {str(e)}"
                        db_session.commit()
                        logging.error(f"Background memory creation failed, marked as deleted: {placeholder_memory_background.id}")
                except Exception as cleanup_error:
                    logging.error(f"Failed to cleanup memory on error: {cleanup_error}")
            finally:
                db_session.close()
        
        # Start the background task
        background_task = asyncio.create_task(create_memory_background())
        
        return placeholder_memory, background_task
        
    finally:
        db.close()
