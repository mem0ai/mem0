import logging
import os
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import uvicorn

from mem0 import Memory

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/app/logs/mem0-server.log", mode="a")
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables with fallback to production config
load_dotenv()
if os.path.exists(".env.production"):
    load_dotenv(".env.production", override=True)

# Enhanced configuration with production optimizations
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.environ.get("POSTGRES_DB", "whatsapp_assistant")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")
POSTGRES_COLLECTION_NAME = os.environ.get("POSTGRES_COLLECTION_NAME", "mem0_memories")

# Connection pool settings
POSTGRES_POOL_SIZE = int(os.environ.get("POSTGRES_POOL_SIZE", "20"))
POSTGRES_MAX_OVERFLOW = int(os.environ.get("POSTGRES_MAX_OVERFLOW", "30"))
POSTGRES_POOL_TIMEOUT = int(os.environ.get("POSTGRES_POOL_TIMEOUT", "30"))

# Graph database configuration
AGE_ENABLED = os.environ.get("AGE_ENABLED", "true").lower() == "true"
NEO4J_ENABLED = os.environ.get("NEO4J_ENABLED", "false").lower() == "true"
MEMGRAPH_ENABLED = os.environ.get("MEMGRAPH_ENABLED", "false").lower() == "true"

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "mem0graph")

MEMGRAPH_URI = os.environ.get("MEMGRAPH_URI", "bolt://localhost:7687")
MEMGRAPH_USERNAME = os.environ.get("MEMGRAPH_USERNAME", "memgraph")
MEMGRAPH_PASSWORD = os.environ.get("MEMGRAPH_PASSWORD", "mem0graph")

# LLM Configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
AZURE_OPENAI_ENABLED = os.environ.get("AZURE_OPENAI_ENABLED", "false").lower() == "true"
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-01")

# Server configuration
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
WORKERS = int(os.environ.get("WORKERS", "4"))
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

HISTORY_DB_PATH = os.environ.get("HISTORY_DB_PATH", "/app/data/history.db")

# Enhanced configuration with production optimizations
def get_optimized_config() -> Dict[str, Any]:
    """Get optimized mem0 configuration for production deployment."""

    # Base configuration
    config = {
        "version": "v1.1",
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "host": POSTGRES_HOST,
                "port": POSTGRES_PORT,
                "dbname": POSTGRES_DB,
                "user": POSTGRES_USER,
                "password": POSTGRES_PASSWORD,
                "collection_name": POSTGRES_COLLECTION_NAME,
                "embedding_model_dims": int(os.environ.get("EMBEDDING_DIMENSIONS", "1536")),
                "hnsw": True,  # Enable HNSW indexing for better performance
                "ef_construction": int(os.environ.get("PGVECTOR_EF_CONSTRUCTION", "200")),
                "ef_search": int(os.environ.get("PGVECTOR_EF_SEARCH", "100")),
                "max_connections": int(os.environ.get("PGVECTOR_MAX_CONNECTIONS", "16")),
                # Connection pool settings
                "pool_size": POSTGRES_POOL_SIZE,
                "max_overflow": POSTGRES_MAX_OVERFLOW,
                "pool_timeout": POSTGRES_POOL_TIMEOUT,
                "pool_recycle": int(os.environ.get("POSTGRES_POOL_RECYCLE", "3600")),
                "pool_pre_ping": True,
            },
        },
        "history_db_path": HISTORY_DB_PATH,
    }

    # Configure LLM provider
    if AZURE_OPENAI_ENABLED and AZURE_OPENAI_API_KEY:
        config["llm"] = {
            "provider": "azure_openai",
            "config": {
                "api_key": AZURE_OPENAI_API_KEY,
                "azure_endpoint": AZURE_OPENAI_ENDPOINT,
                "api_version": AZURE_OPENAI_API_VERSION,
                "model": os.environ.get("AZURE_OPENAI_MODEL", "gpt-4"),
                "temperature": float(os.environ.get("OPENAI_TEMPERATURE", "0.2")),
                "max_tokens": int(os.environ.get("OPENAI_MAX_TOKENS", "1000")),
            }
        }
        config["embedder"] = {
            "provider": "azure_openai",
            "config": {
                "api_key": AZURE_OPENAI_API_KEY,
                "azure_endpoint": AZURE_OPENAI_ENDPOINT,
                "api_version": AZURE_OPENAI_API_VERSION,
                "model": os.environ.get("AZURE_OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"),
            }
        }
    else:
        config["llm"] = {
            "provider": "openai",
            "config": {
                "api_key": OPENAI_API_KEY,
                "model": os.environ.get("OPENAI_MODEL", "gpt-4o"),
                "temperature": float(os.environ.get("OPENAI_TEMPERATURE", "0.2")),
                "max_tokens": int(os.environ.get("OPENAI_MAX_TOKENS", "1000")),
            }
        }
        config["embedder"] = {
            "provider": "openai",
            "config": {
                "api_key": OPENAI_API_KEY,
                "model": os.environ.get("EMBEDDING_MODEL", "text-embedding-3-large"),
            }
        }

    # Configure graph store based on enabled provider
    if AGE_ENABLED:
        config["graph_store"] = {
            "provider": "apache_age",
            "config": {
                "host": os.environ.get("AGE_HOST", POSTGRES_HOST),
                "port": int(os.environ.get("AGE_PORT", str(POSTGRES_PORT))),
                "database": os.environ.get("AGE_DATABASE", POSTGRES_DB),
                "username": os.environ.get("AGE_USERNAME", POSTGRES_USER),
                "password": os.environ.get("AGE_PASSWORD", POSTGRES_PASSWORD),
                "graph_name": os.environ.get("AGE_GRAPH_NAME", "memory_graph"),
                "base_label": True,
            }
        }
    elif NEO4J_ENABLED:
        config["graph_store"] = {
            "provider": "neo4j",
            "config": {
                "url": NEO4J_URI,
                "username": NEO4J_USERNAME,
                "password": NEO4J_PASSWORD,
            }
        }
    elif MEMGRAPH_ENABLED:
        config["graph_store"] = {
            "provider": "memgraph",
            "config": {
                "url": MEMGRAPH_URI,
                "username": MEMGRAPH_USERNAME,
                "password": MEMGRAPH_PASSWORD,
            }
        }

    return config

DEFAULT_CONFIG = get_optimized_config()


# Global memory instance
MEMORY_INSTANCE = None

# Security configuration
security = HTTPBearer() if os.environ.get("API_KEY_ENABLED", "false").lower() == "true" else None
API_KEY = os.environ.get("API_KEY")

# CORS configuration
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", '["*"]')
if isinstance(CORS_ORIGINS, str):
    import json
    try:
        CORS_ORIGINS = json.loads(CORS_ORIGINS)
    except json.JSONDecodeError:
        CORS_ORIGINS = ["*"]

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    global MEMORY_INSTANCE

    # Startup
    logger.info("Starting mem0 server with optimized configuration...")
    try:
        MEMORY_INSTANCE = Memory.from_config(DEFAULT_CONFIG)
        logger.info("Memory instance initialized successfully")

        # Test the connection
        test_result = await test_memory_connection()
        if test_result:
            logger.info("Memory connection test passed")
        else:
            logger.warning("Memory connection test failed, but continuing...")

    except Exception as e:
        logger.error(f"Failed to initialize memory instance: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down mem0 server...")
    if MEMORY_INSTANCE:
        try:
            # Perform any cleanup if needed
            logger.info("Memory instance cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

app = FastAPI(
    title="Self-Hosted Mem0 REST APIs",
    description="A production-ready REST API for managing and searching memories for AI WhatsApp Assistant and other AI Agents.",
    version="2.0.0",
    lifespan=lifespan,
    debug=DEBUG,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=os.environ.get("CORS_CREDENTIALS", "true").lower() == "true",
    allow_methods=os.environ.get("CORS_METHODS", '["GET", "POST", "PUT", "DELETE", "OPTIONS"]'),
    allow_headers=os.environ.get("CORS_HEADERS", '["*"]'),
)

# Security dependency
async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> bool:
    """Verify API key if security is enabled."""
    if security and API_KEY:
        if credentials.credentials != API_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
    return True

async def test_memory_connection() -> bool:
    """Test memory instance connection."""
    try:
        if MEMORY_INSTANCE:
            # Try a simple operation to test the connection
            test_memories = MEMORY_INSTANCE.get_all(user_id="test_connection_user")
            return True
    except Exception as e:
        logger.error(f"Memory connection test failed: {e}")
        return False
    return False


class Message(BaseModel):
    role: str = Field(..., description="Role of the message (user or assistant).")
    content: str = Field(..., description="Message content.")


class MemoryCreate(BaseModel):
    messages: List[Message] = Field(..., description="List of messages to store.")
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query.")
    user_id: Optional[str] = None
    run_id: Optional[str] = None
    agent_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None


@app.get("/health", summary="Health check", include_in_schema=True)
async def health_check():
    """Health check endpoint for monitoring."""
    try:
        connection_status = await test_memory_connection()
        return {
            "status": "healthy" if connection_status else "degraded",
            "timestamp": os.environ.get("TIMESTAMP", "unknown"),
            "version": "2.0.0",
            "memory_instance": MEMORY_INSTANCE is not None,
            "database_connection": connection_status,
            "graph_enabled": AGE_ENABLED or NEO4J_ENABLED or MEMGRAPH_ENABLED,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")

@app.get("/config", summary="Get current configuration")
async def get_config(authorized: bool = Depends(verify_api_key) if security else True):
    """Get current memory configuration (sensitive data masked)."""
    try:
        config = DEFAULT_CONFIG.copy()
        # Mask sensitive information
        if "llm" in config and "config" in config["llm"]:
            config["llm"]["config"]["api_key"] = "***masked***"
        if "embedder" in config and "config" in config["embedder"]:
            config["embedder"]["config"]["api_key"] = "***masked***"
        if "vector_store" in config and "config" in config["vector_store"]:
            config["vector_store"]["config"]["password"] = "***masked***"
        if "graph_store" in config and "config" in config["graph_store"]:
            config["graph_store"]["config"]["password"] = "***masked***"

        return {"config": config, "status": "active"}
    except Exception as e:
        logger.error(f"Error getting configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/configure", summary="Configure Mem0")
async def set_config(
    config: Dict[str, Any],
    authorized: bool = Depends(verify_api_key) if security else True
):
    """Set memory configuration with validation."""
    global MEMORY_INSTANCE
    try:
        # Validate configuration
        if not config:
            raise HTTPException(status_code=400, detail="Configuration cannot be empty")

        # Create new memory instance with provided config
        new_instance = Memory.from_config(config)

        # Test the new configuration
        test_memories = new_instance.get_all(user_id="config_test_user")

        # If successful, update the global instance
        MEMORY_INSTANCE = new_instance
        logger.info("Memory configuration updated successfully")

        return {"message": "Configuration set successfully", "status": "updated"}
    except Exception as e:
        logger.error(f"Error setting configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Configuration update failed: {str(e)}")


@app.post("/memories", summary="Create memories")
async def add_memory(
    memory_create: MemoryCreate,
    authorized: bool = Depends(verify_api_key) if security else True
):
    """Store new memories with enhanced validation and error handling."""
    if not MEMORY_INSTANCE:
        raise HTTPException(status_code=503, detail="Memory service not available")

    if not any([memory_create.user_id, memory_create.agent_id, memory_create.run_id]):
        raise HTTPException(
            status_code=400,
            detail="At least one identifier (user_id, agent_id, run_id) is required."
        )

    # Validate messages
    if not memory_create.messages:
        raise HTTPException(status_code=400, detail="Messages cannot be empty")

    # Validate message content
    for i, message in enumerate(memory_create.messages):
        if not message.content or not message.content.strip():
            raise HTTPException(
                status_code=400,
                detail=f"Message {i} content cannot be empty"
            )

    params = {k: v for k, v in memory_create.model_dump().items() if v is not None and k != "messages"}

    try:
        logger.info(f"Adding memory for user: {memory_create.user_id}, messages: {len(memory_create.messages)}")

        response = MEMORY_INSTANCE.add(
            messages=[m.model_dump() for m in memory_create.messages],
            **params
        )

        logger.info(f"Memory added successfully: {response}")
        return JSONResponse(content=response)

    except Exception as e:
        logger.exception(f"Error in add_memory for user {memory_create.user_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add memory: {str(e)}"
        )


@app.get("/memories", summary="Get memories")
def get_all_memories(
    user_id: Optional[str] = None,
    run_id: Optional[str] = None,
    agent_id: Optional[str] = None,
):
    """Retrieve stored memories."""
    if not any([user_id, run_id, agent_id]):
        raise HTTPException(status_code=400, detail="At least one identifier is required.")
    try:
        params = {
            k: v for k, v in {"user_id": user_id, "run_id": run_id, "agent_id": agent_id}.items() if v is not None
        }
        return MEMORY_INSTANCE.get_all(**params)
    except Exception as e:
        logging.exception("Error in get_all_memories:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memories/{memory_id}", summary="Get a memory")
def get_memory(memory_id: str):
    """Retrieve a specific memory by ID."""
    try:
        return MEMORY_INSTANCE.get(memory_id)
    except Exception as e:
        logging.exception("Error in get_memory:")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search", summary="Search memories")
def search_memories(search_req: SearchRequest):
    """Search for memories based on a query."""
    try:
        params = {k: v for k, v in search_req.model_dump().items() if v is not None and k != "query"}
        return MEMORY_INSTANCE.search(query=search_req.query, **params)
    except Exception as e:
        logging.exception("Error in search_memories:")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/memories/{memory_id}", summary="Update a memory")
def update_memory(memory_id: str, updated_memory: Dict[str, Any]):
    """Update an existing memory with new content.
    
    Args:
        memory_id (str): ID of the memory to update
        updated_memory (str): New content to update the memory with
        
    Returns:
        dict: Success message indicating the memory was updated
    """
    try:
        return MEMORY_INSTANCE.update(memory_id=memory_id, data=updated_memory)
    except Exception as e:
        logging.exception("Error in update_memory:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memories/{memory_id}/history", summary="Get memory history")
def memory_history(memory_id: str):
    """Retrieve memory history."""
    try:
        return MEMORY_INSTANCE.history(memory_id=memory_id)
    except Exception as e:
        logging.exception("Error in memory_history:")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/memories/{memory_id}", summary="Delete a memory")
def delete_memory(memory_id: str):
    """Delete a specific memory by ID."""
    try:
        MEMORY_INSTANCE.delete(memory_id=memory_id)
        return {"message": "Memory deleted successfully"}
    except Exception as e:
        logging.exception("Error in delete_memory:")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/memories", summary="Delete all memories")
def delete_all_memories(
    user_id: Optional[str] = None,
    run_id: Optional[str] = None,
    agent_id: Optional[str] = None,
):
    """Delete all memories for a given identifier."""
    if not any([user_id, run_id, agent_id]):
        raise HTTPException(status_code=400, detail="At least one identifier is required.")
    try:
        params = {
            k: v for k, v in {"user_id": user_id, "run_id": run_id, "agent_id": agent_id}.items() if v is not None
        }
        MEMORY_INSTANCE.delete_all(**params)
        return {"message": "All relevant memories deleted"}
    except Exception as e:
        logging.exception("Error in delete_all_memories:")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reset", summary="Reset all memories")
def reset_memory():
    """Completely reset stored memories."""
    try:
        MEMORY_INSTANCE.reset()
        return {"message": "All memories reset"}
    except Exception as e:
        logging.exception("Error in reset_memory:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", summary="Redirect to the OpenAPI documentation", include_in_schema=False)
def home():
    """Redirect to the OpenAPI documentation."""
    return RedirectResponse(url="/docs")
