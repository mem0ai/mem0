"""
Memory client configuration management for OpenMemory.

This module provides configuration functions for the memory client,
using a simplified approach that avoids complex import dependencies.
"""

import os
import logging
from typing import Dict, Any


def _detect_docker_environment() -> bool:
    """Detect if we're running inside a Docker container."""
    return os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'


def _get_docker_host_url(original_url: str) -> str:

    
    
    """Adjust localhost URLs for Docker environment."""
    if not _detect_docker_environment():
        return original_url
    
    # Check for explicit OLLAMA_HOST setting
    ollama_host = os.environ.get('OLLAMA_HOST')
    if ollama_host:
        return original_url.replace('localhost', ollama_host)
    
    # Try different Docker host resolution strategies
    import socket
    docker_hosts = [
        'host.docker.internal',  # Docker Desktop for Mac/Windows
        '172.17.0.1',           # Docker bridge gateway (Linux)
    ]
    
    for host in docker_hosts:
        try:
            # Test if the host is reachable
            socket.create_connection((host, 11434), timeout=1)
            return original_url.replace('localhost', host)
        except (socket.error, OSError):
            continue
    
    # Fallback to bridge gateway
    return original_url.replace('localhost', '172.17.0.1')


def get_memory_config_dict() -> Dict[str, Any]:
    """Get memory configuration as a dictionary for the memory client."""
    # Adjust base URL for Docker if needed
    base_url = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    if base_url.startswith('http://localhost'):
        base_url = _get_docker_host_url(base_url)
    
    config = {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "openmemory",
                "host": os.environ.get('QDRANT_HOST', 'qdrant.root.svc.cluster.local'),
                "port": int(os.environ.get('QDRANT_PORT', 6333)),
                "api_key": os.environ.get('QDRANT_API_KEY'),
            }
        },
        "graph_store": {
            "provider": "neo4j",
            "config": {
                "url": os.environ.get('NEO4J_URL', 'neo4j://neo4j'),
                "username": os.environ.get('NEO4J_USERNAME', 'neo4j'),
                "password": os.environ.get('NEO4J_PASSWORD'),
                "database": os.environ.get('NEO4J_DB', 'neo4j'),
            },
            "llm": None,
            "custom_prompt": None
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
    
    # Only add base_url if it's not the default
    if base_url != 'https://api.openai.com/v1':
        config["llm"]["config"]["openai_base_url"] = base_url
        config["embedder"]["config"]["openai_base_url"] = base_url
    
    # Log configuration for debugging
    logging.info(f"Memory config - Vector store: {config['vector_store']['provider']}")
    logging.info(f"Memory config - Graph store: {config['graph_store']['provider']}")
    logging.info(f"Memory config - LLM: {config['llm']['provider']}")
    
    return config
