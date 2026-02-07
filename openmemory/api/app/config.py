import json
import os
import logging
from typing import Dict, Any

# Get logger
logger = logging.getLogger(__name__)

USER_ID = os.getenv("USER", "default_user")
DEFAULT_APP_ID = "openmemory"

def load_config() -> Dict[str, Any]:
    """
    Load configuration from config.json and merge with environment variables.
    
    Returns:
        Dict containing the merged configuration
    """
    config = {}
    
    # 1. Load from config.json
    try:
        # Determine the path to config.json
        # Assuming config.json is in the api directory, which is the parent of app
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up one level to get to api directory (app -> api)
        api_dir = os.path.dirname(current_dir)
        config_path = os.path.join(api_dir, "config.json")
        
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
            logger.info(f"Loaded configuration from {config_path}, config: {config}")
        else:
            logger.warning(f"Config file not found at {config_path}, using empty defaults")
    except Exception as e:
        logger.error(f"Error loading config.json: {e}")
        # Continue with empty config if file load fails
    
    # Ensure structure exists
    if "mem0" not in config:
        config["mem0"] = {}
    
    # 2. Detect vector store from environment variables (dynamic configuration)
    vector_store_config = _detect_vector_store_config()
    if vector_store_config:
        config["mem0"]["vector_store"] = vector_store_config
    
    # Check if vector store config exists (either from json or env), if not use default
    if "vector_store" not in config.get("mem0", {}):
        logger.info("No vector store config found in json or env, using default Qdrant config")
        config["mem0"]["vector_store"] = {
            "provider": "qdrant",
            "config": {
                "collection_name": "openmemory",
                "host": "mem0_store",
                "port": 6333,
            }
        }
    
    # 3. Add version if not present
    if "version" not in config:
        config["version"] = "v1.1"
        
    # 4. Ensure openmemory section exists
    if "openmemory" not in config:
        config["openmemory"] = {"custom_instructions": None}
        
    return config

def _detect_vector_store_config() -> Dict[str, Any]:
    """
    Detect vector store configuration from environment variables.
    
    Returns:
        Dict containing vector store configuration or None if detection fails
    """
    vector_store_config = {}
    vector_store_provider = "qdrant"
    
    # Check for different vector store configurations based on environment variables
    if os.environ.get('CHROMA_HOST') and os.environ.get('CHROMA_PORT'):
        vector_store_provider = "chroma"
        vector_store_config = {
            "collection_name": "openmemory",
            "host": os.environ.get('CHROMA_HOST'),
            "port": int(os.environ.get('CHROMA_PORT'))
        }
    elif os.environ.get('QDRANT_HOST') and os.environ.get('QDRANT_PORT'):
        vector_store_provider = "qdrant"
        vector_store_config = {
            "collection_name": "openmemory",
            "host": os.environ.get('QDRANT_HOST'),
            "port": int(os.environ.get('QDRANT_PORT'))
        }
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
        vector_store_config = {
            "host": os.environ.get('PG_HOST'),
            "port": int(os.environ.get('PG_PORT')),
            "dbname": os.environ.get('PG_DB', 'mem0'),
            "user": os.environ.get('PG_USER', 'mem0'),
            "password": os.environ.get('PG_PASSWORD', 'mem0'),
            "collection_name": "openmemory"
        }
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
        
        vector_store_config = {
            "host": full_host,
            "port": elasticsearch_port,
            "user": os.environ.get('ELASTICSEARCH_USER', 'elastic'),
            "password": os.environ.get('ELASTICSEARCH_PASSWORD', 'changeme'),
            "verify_certs": False,
            "use_ssl": False,
            "embedding_model_dims": 1536,
            "collection_name": "openmemory"
        }
    elif os.environ.get('OPENSEARCH_HOST') and os.environ.get('OPENSEARCH_PORT'):
        vector_store_provider = "opensearch"
        vector_store_config = {
            "host": os.environ.get('OPENSEARCH_HOST'),
            "port": int(os.environ.get('OPENSEARCH_PORT')),
            "collection_name": "openmemory"
        }
    elif os.environ.get('FAISS_PATH'):
        vector_store_provider = "faiss"
        vector_store_config = {
            "collection_name": "openmemory",
            "path": os.environ.get('FAISS_PATH'),
            "embedding_model_dims": 1536,
            "distance_strategy": "cosine"
        }
    else:
        # No vector store configuration found in environment variables
        return None
    
    logger.info(f"Auto-detected vector store: {vector_store_provider} with config: {vector_store_config}")
    
    return {
        "provider": vector_store_provider,
        "config": vector_store_config
    }
