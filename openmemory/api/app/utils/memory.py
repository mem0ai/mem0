import os
import sys
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Calculate project root more explicitly
# Current file path: /path/to/your-memory/openmemory/api/app/utils/memory.py
# Project root path: /path/to/your-memory/
current_dir = Path(__file__).parent.resolve()  # app/utils/
api_dir = current_dir.parent.parent  # openmemory/api/
openmemory_dir = api_dir.parent  # openmemory/
project_root = openmemory_dir.parent  # your-memory/

# Add project root to Python path
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from jean_memory_v2.mem0_adapter_optimized import get_memory_client_v2_optimized
from app.settings import config  # Import the application config


def get_memory_client(custom_instructions: str = None):
    """
    Initializes and returns a Jean Memory V2 client with mem0 compatibility.
    Provides enhanced multi-source memory (mem0 + Graphiti) while maintaining 100% API compatibility.
    """
    try:
        # Jean Memory V2 handles all configuration internally using environment variables
        # It automatically configures both mem0 (Qdrant) and Graphiti (Neo4j) backends
        
        # Verify required environment variables are set
        qdrant_host = os.getenv("QDRANT_HOST")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # For local development (localhost), QDRANT_API_KEY is optional
        # For cloud deployment, QDRANT_API_KEY is required
        required_vars = ["QDRANT_HOST", "OPENAI_API_KEY"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        # Check if QDRANT_API_KEY is required (cloud deployment)
        if qdrant_host and qdrant_host != "localhost" and not qdrant_api_key:
            missing_vars.append("QDRANT_API_KEY")
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables for Jean Memory V2: {missing_vars}")
        
        # Optional: Check for Neo4j variables (used by Graphiti backend)
        neo4j_vars = ["NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"]
        neo4j_available = all(os.getenv(var) for var in neo4j_vars)
        
        if not neo4j_available:
            logger.warning("Neo4j variables not found - Jean Memory V2 will run in mem0-only mode")
            logger.info("To enable graph memory, set: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD")
        
        # Get Jean Memory V2 OPTIMIZED adapter - provides 100% mem0 API compatibility with 3-5x performance
        # The adapter automatically handles async/sync contexts
        memory_instance = get_memory_client_v2_optimized()
        
        logger.info("Jean Memory V2 initialized successfully - Enhanced multi-source memory ready")
        return memory_instance

    except Exception as e:
        # Enhanced logging
        logger.error(f"Error initializing Jean Memory V2 client: {e}")
        logger.info("Falling back to basic configuration...")
        raise Exception(f"Could not initialize Jean Memory V2 client: {e}")


async def get_async_memory_client(custom_instructions: str = None):
    """
    Initializes and returns an async Jean Memory V2 client with mem0-compatible API.
    This is the async version for use in FastAPI endpoints.
    """
    try:
        # Import OPTIMIZED async adapter
        from jean_memory_v2.mem0_adapter_optimized import get_async_memory_client_v2_optimized
        
        # Verify required environment variables are set (same as sync version)
        qdrant_host = os.getenv("QDRANT_HOST")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        
        # For local development (localhost), QDRANT_API_KEY is optional
        # For cloud deployment, QDRANT_API_KEY is required
        required_vars = ["QDRANT_HOST", "OPENAI_API_KEY"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        # Check if QDRANT_API_KEY is required (cloud deployment)
        if qdrant_host and qdrant_host != "localhost" and not qdrant_api_key:
            missing_vars.append("QDRANT_API_KEY")
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables for Jean Memory V2: {missing_vars}")
        
        # Optional: Check for Neo4j variables (used by Graphiti backend)
        neo4j_vars = ["NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"]
        neo4j_available = all(os.getenv(var) for var in neo4j_vars)
        
        if not neo4j_available:
            logger.warning("Neo4j variables not found - Jean Memory V2 will run in mem0-only mode")
            logger.info("To enable graph memory, set: NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD")
        
        # Validate environment variables
        logger.debug("Checking environment variables for Jean Memory V2 configuration")
        
        # Create config from current environment variables (FIXED: No hardcoded values)
        from jean_memory_v2.config import JeanMemoryConfig
        
        # Get actual environment values - NO HARDCODED FALLBACKS
        neo4j_uri_env = os.getenv("NEO4J_URI")
        neo4j_user_env = os.getenv("NEO4J_USER") 
        neo4j_password_env = os.getenv("NEO4J_PASSWORD")
        
        # Validate critical environment variables
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY is required but not set in environment")
            
        if not qdrant_host:
            raise ValueError("QDRANT_HOST is required but not set in environment")
        
        config_dict = {
            'OPENAI_API_KEY': openai_api_key,  # FIXED: Use actual environment value
            'QDRANT_HOST': qdrant_host,
            'QDRANT_PORT': os.getenv("QDRANT_PORT", "6333"),
            'QDRANT_API_KEY': qdrant_api_key or "",  # Empty string for localhost
            'NEO4J_URI': neo4j_uri_env,  # May be None if not configured
            'NEO4J_USER': neo4j_user_env,  # May be None if not configured
            'NEO4J_PASSWORD': neo4j_password_env,  # May be None if not configured
            'GEMINI_API_KEY': os.getenv("GEMINI_API_KEY") or "",
            'MAIN_QDRANT_COLLECTION_NAME': os.getenv("MAIN_QDRANT_COLLECTION_NAME", "openmemory_dev")
        }
        
        logger.debug("Initializing Jean Memory V2 with environment configuration")
        
        # Create config from environment variables (clean config without hardcoded values)
        config = JeanMemoryConfig.from_dict(config_dict)
        
        # Get async Jean Memory V2 OPTIMIZED adapter with explicit config
        memory_instance = get_async_memory_client_v2_optimized(config={'jean_memory_config': config})
        
        logger.info("✅ Async Jean Memory V2 OPTIMIZED initialized successfully - Enhanced multi-source memory ready (3-5x faster)")
        return memory_instance

    except Exception as e:
        # Enhanced logging
        logger.error(f"Error initializing async Jean Memory V2 client: {e}")
        logger.info("Falling back to basic configuration...")
        raise Exception(f"Could not initialize async Jean Memory V2 client: {e}")
