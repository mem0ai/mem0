import json
import logging
import os
from urllib.parse import quote_plus
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from mem0 import Memory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Load environment variables
load_dotenv()


POSTGRES_HOST_ENV = os.environ.get("POSTGRES_HOST")
POSTGRES_PORT_ENV = os.environ.get("POSTGRES_PORT")
POSTGRES_DB_ENV = os.environ.get("POSTGRES_DB")
POSTGRES_USER_ENV = os.environ.get("POSTGRES_USER")
POSTGRES_PASSWORD_ENV = os.environ.get("POSTGRES_PASSWORD")

POSTGRES_HOST = POSTGRES_HOST_ENV or "postgres"
POSTGRES_PORT = POSTGRES_PORT_ENV or "5432"
POSTGRES_DB = POSTGRES_DB_ENV or "postgres"
POSTGRES_USER = POSTGRES_USER_ENV or "postgres"
POSTGRES_PASSWORD = POSTGRES_PASSWORD_ENV or "postgres"
POSTGRES_COLLECTION_NAME = os.environ.get("POSTGRES_COLLECTION_NAME", "memories")

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "mem0graph")

MEMGRAPH_URI = os.environ.get("MEMGRAPH_URI", "bolt://localhost:7687")
MEMGRAPH_USERNAME = os.environ.get("MEMGRAPH_USERNAME", "memgraph")
MEMGRAPH_PASSWORD = os.environ.get("MEMGRAPH_PASSWORD", "mem0graph")

GRAPH_STORE_PROVIDER = os.environ.get("GRAPH_STORE_PROVIDER")
KUZU_DB_PATH = os.environ.get("KUZU_DB_PATH", ":memory:")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
LLM_PROVIDER = os.environ.get("LLM_PROVIDER")
LLM_API_KEY = os.environ.get("LLM_API_KEY")
LLM_MODEL = os.environ.get("LLM_MODEL")
LLM_TEMPERATURE = os.environ.get("LLM_TEMPERATURE")
LLM_MAX_TOKENS = os.environ.get("LLM_MAX_TOKENS")
LLM_TOP_P = os.environ.get("LLM_TOP_P")
LLM_AZURE_OPENAI_API_KEY = os.environ.get("LLM_AZURE_OPENAI_API_KEY")
LLM_AZURE_DEPLOYMENT = os.environ.get("LLM_AZURE_DEPLOYMENT")
LLM_AZURE_ENDPOINT = os.environ.get("LLM_AZURE_ENDPOINT")
LLM_AZURE_API_VERSION = os.environ.get("LLM_AZURE_API_VERSION")

EMBEDDING_AZURE_OPENAI_API_KEY = os.environ.get("EMBEDDING_AZURE_OPENAI_API_KEY")
EMBEDDING_AZURE_DEPLOYMENT = os.environ.get("EMBEDDING_AZURE_DEPLOYMENT")
EMBEDDING_AZURE_ENDPOINT = os.environ.get("EMBEDDING_AZURE_ENDPOINT")
EMBEDDING_AZURE_API_VERSION = os.environ.get("EMBEDDING_AZURE_API_VERSION")
EMBEDDER_PROVIDER = os.environ.get("EMBEDDER_PROVIDER")
EMBEDDING_API_KEY = os.environ.get("EMBEDDING_API_KEY")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL")
EMBEDDING_DIMS = os.environ.get("EMBEDDING_DIMS")
HUGGINGFACE_BASE_URL = os.environ.get("HUGGINGFACE_BASE_URL")
HUGGINGFACE_MODEL_KWARGS = os.environ.get("HUGGINGFACE_MODEL_KWARGS")
VERTEX_CREDENTIALS_JSON = os.environ.get("VERTEX_CREDENTIALS_JSON")
VERTEX_PROJECT_ID = os.environ.get("VERTEX_PROJECT_ID")
GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GEMINI_OUTPUT_DIM = os.environ.get("GEMINI_OUTPUT_DIM")
EMBEDDING_OLLAMA_BASE_URL = os.environ.get("EMBEDDING_OLLAMA_BASE_URL") or OLLAMA_BASE_URL
EMBEDDING_LMSTUDIO_BASE_URL = os.environ.get("EMBEDDING_LMSTUDIO_BASE_URL") or LMSTUDIO_BASE_URL
EMBEDDING_AWS_REGION = os.environ.get("EMBEDDING_AWS_REGION")
EMBEDDING_AWS_ACCESS_KEY_ID = os.environ.get("EMBEDDING_AWS_ACCESS_KEY_ID")
EMBEDDING_AWS_SECRET_ACCESS_KEY = os.environ.get("EMBEDDING_AWS_SECRET_ACCESS_KEY")

VLLM_BASE_URL = os.environ.get("VLLM_BASE_URL")
VLLM_API_KEY = os.environ.get("VLLM_API_KEY")
VLLM_MODEL = os.environ.get("VLLM_MODEL")
VLLM_TEMPERATURE = os.environ.get("VLLM_TEMPERATURE")
VLLM_MAX_TOKENS = os.environ.get("VLLM_MAX_TOKENS")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL")
DEEPSEEK_API_BASE = os.environ.get("DEEPSEEK_API_BASE")
LMSTUDIO_BASE_URL = os.environ.get("LMSTUDIO_BASE_URL")
LMSTUDIO_RESPONSE_FORMAT = os.environ.get("LMSTUDIO_RESPONSE_FORMAT")
HISTORY_DB_PATH = os.environ.get("HISTORY_DB_PATH", "/app/history/history.db")
HISTORY_DB_PROVIDER = os.environ.get("HISTORY_DB_PROVIDER")
HISTORY_DB_URL = os.environ.get("HISTORY_DB_URL")
HISTORY_DB_TABLE = os.environ.get("HISTORY_DB_TABLE", "history")

DEFAULT_CONFIG = {
    "version": "v1.1",
    "vector_store": {
        "provider": "pgvector",
        "config": {
            "host": POSTGRES_HOST,
            "port": int(POSTGRES_PORT),
            "dbname": POSTGRES_DB,
            "user": POSTGRES_USER,
            "password": POSTGRES_PASSWORD,
            "collection_name": POSTGRES_COLLECTION_NAME,
        },
    },
    "graph_store": None,
    "llm": {"provider": "openai", "config": {"api_key": OPENAI_API_KEY, "temperature": 0.2, "model": "gpt-4.1-nano-2025-04-14"}},
    "embedder": {"provider": "openai", "config": {"api_key": OPENAI_API_KEY, "model": "text-embedding-3-small"}},
    "history_db_path": HISTORY_DB_PATH,
    "history_db_provider": HISTORY_DB_PROVIDER,
    "history_db_url": None,
    "history_db_table": HISTORY_DB_TABLE,
}


def _compact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in data.items() if v is not None}


def _normalize_provider(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip().lower()
    if value in {"none", "disabled", "off", "false", "0", ""}:
        return "none"
    return value


def _normalize_llm_provider(value: Optional[str]) -> Optional[str]:
    provider = _normalize_provider(value)
    if provider is None:
        return None
    aliases = {
        "google_ai": "gemini",
        "google": "gemini",
        "mistral_ai": "litellm",
        "mistral": "litellm",
        "azure": "azure_openai",
    }
    return aliases.get(provider, provider)


def _build_graph_store_config() -> Dict[str, Any]:
    provider = _normalize_provider(GRAPH_STORE_PROVIDER)
    if provider == "none":
        return {"provider": "neo4j", "config": None}
    if provider is None:
        if NEO4J_URI and NEO4J_USERNAME and NEO4J_PASSWORD:
            return {
                "provider": "neo4j",
                "config": {"url": NEO4J_URI, "username": NEO4J_USERNAME, "password": NEO4J_PASSWORD},
            }
        return {"provider": "neo4j", "config": None}
    if provider == "neo4j":
        if not (NEO4J_URI and NEO4J_USERNAME and NEO4J_PASSWORD):
            return {"provider": "neo4j", "config": None}
        return {"provider": "neo4j", "config": {"url": NEO4J_URI, "username": NEO4J_USERNAME, "password": NEO4J_PASSWORD}}
    if provider == "memgraph":
        if not (MEMGRAPH_URI and MEMGRAPH_USERNAME and MEMGRAPH_PASSWORD):
            return {"provider": "memgraph", "config": None}
        return {
            "provider": "memgraph",
            "config": {"url": MEMGRAPH_URI, "username": MEMGRAPH_USERNAME, "password": MEMGRAPH_PASSWORD},
        }
    if provider == "kuzu":
        return {"provider": "kuzu", "config": {"db": KUZU_DB_PATH}}
    raise ValueError(f"Unsupported GRAPH_STORE_PROVIDER: {provider}")


def _parse_float(value: Optional[str]) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_json(value: Optional[str]) -> Optional[Dict[str, Any]]:
    if value is None or value == "":
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        raise ValueError("LMSTUDIO_RESPONSE_FORMAT must be valid JSON")


def _normalize_embedder_provider(value: Optional[str]) -> Optional[str]:
    provider = _normalize_provider(value)
    if provider is None:
        return None
    aliases = {
        "google_ai": "gemini",
        "google": "gemini",
    }
    return aliases.get(provider, provider)


def _build_history_db_url() -> Optional[str]:
    if HISTORY_DB_URL:
        return HISTORY_DB_URL
    if not (POSTGRES_HOST and POSTGRES_PORT and POSTGRES_DB and POSTGRES_USER):
        return None
    user = quote_plus(POSTGRES_USER)
    password = quote_plus(POSTGRES_PASSWORD) if POSTGRES_PASSWORD else None
    auth = f"{user}:{password}@" if password else f"{user}@"
    return f"postgresql://{auth}{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"


DEFAULT_CONFIG["graph_store"] = _build_graph_store_config()

def _resolve_history_provider() -> str:
    provider = _normalize_provider(HISTORY_DB_PROVIDER)
    if provider == "none":
        return "sqlite"
    if provider:
        return provider
    if HISTORY_DB_URL:
        return "postgres"
    if any([POSTGRES_HOST_ENV, POSTGRES_PORT_ENV, POSTGRES_DB_ENV, POSTGRES_USER_ENV, POSTGRES_PASSWORD_ENV]):
        return "postgres"
    return "sqlite"


_HISTORY_PROVIDER = _resolve_history_provider()
DEFAULT_CONFIG["history_db_provider"] = _HISTORY_PROVIDER
DEFAULT_CONFIG["history_db_url"] = _build_history_db_url() if _HISTORY_PROVIDER in {"postgres", "postgresql", "pg"} else None


def _azure_llm_config():
    llm_model = LLM_MODEL or LLM_AZURE_DEPLOYMENT
    return {
        "provider": "azure_openai",
        "config": {
            "model": llm_model,
            "temperature": 0.2,
            "azure_kwargs": {
                "api_key": LLM_AZURE_OPENAI_API_KEY,
                "azure_deployment": LLM_AZURE_DEPLOYMENT,
                "azure_endpoint": LLM_AZURE_ENDPOINT,
                "api_version": LLM_AZURE_API_VERSION,
            },
        },
    }


def _azure_embedder_config():
    embedding_model = os.environ.get("EMBEDDING_MODEL") or EMBEDDING_AZURE_DEPLOYMENT
    return {
        "provider": "azure_openai",
        "config": {
            "model": embedding_model,
            "azure_kwargs": {
                "api_key": EMBEDDING_AZURE_OPENAI_API_KEY,
                "azure_deployment": EMBEDDING_AZURE_DEPLOYMENT,
                "azure_endpoint": EMBEDDING_AZURE_ENDPOINT,
                "api_version": EMBEDDING_AZURE_API_VERSION,
            },
        },
    }


def _vllm_llm_config():
    return {
        "provider": "vllm",
        "config": _compact_dict(
            {
                "model": VLLM_MODEL or LLM_MODEL,
                "vllm_base_url": VLLM_BASE_URL,
                "api_key": VLLM_API_KEY or LLM_API_KEY,
                "temperature": _parse_float(VLLM_TEMPERATURE or LLM_TEMPERATURE),
                "max_tokens": _parse_int(VLLM_MAX_TOKENS or LLM_MAX_TOKENS),
                "top_p": _parse_float(LLM_TOP_P),
            }
        ),
    }


def _build_llm_config(provider: str) -> Dict[str, Any]:
    config = _compact_dict(
        {
            "model": LLM_MODEL,
            "temperature": _parse_float(LLM_TEMPERATURE),
            "max_tokens": _parse_int(LLM_MAX_TOKENS),
            "top_p": _parse_float(LLM_TOP_P),
            "api_key": LLM_API_KEY,
        }
    )

    if provider == "ollama":
        config["ollama_base_url"] = OLLAMA_BASE_URL
    elif provider == "deepseek":
        config["deepseek_base_url"] = DEEPSEEK_API_BASE
    elif provider == "lmstudio":
        if LMSTUDIO_BASE_URL:
            config["lmstudio_base_url"] = LMSTUDIO_BASE_URL
        if LMSTUDIO_RESPONSE_FORMAT:
            config["lmstudio_response_format"] = _parse_json(LMSTUDIO_RESPONSE_FORMAT)
    return _compact_dict(config)


def _build_embedder_config(provider: str) -> Dict[str, Any]:
    config = _compact_dict(
        {
            "model": EMBEDDING_MODEL,
            "api_key": EMBEDDING_API_KEY,
            "embedding_dims": _parse_int(EMBEDDING_DIMS),
        }
    )

    if provider == "ollama":
        config["ollama_base_url"] = EMBEDDING_OLLAMA_BASE_URL
    elif provider == "huggingface":
        if HUGGINGFACE_BASE_URL:
            config["huggingface_base_url"] = HUGGINGFACE_BASE_URL
        if HUGGINGFACE_MODEL_KWARGS:
            config["model_kwargs"] = _parse_json(HUGGINGFACE_MODEL_KWARGS)
    elif provider == "vertexai":
        if VERTEX_CREDENTIALS_JSON:
            config["vertex_credentials_json"] = VERTEX_CREDENTIALS_JSON
        if VERTEX_PROJECT_ID:
            config["google_project_id"] = VERTEX_PROJECT_ID
        if GOOGLE_SERVICE_ACCOUNT_JSON:
            config["google_service_account_json"] = GOOGLE_SERVICE_ACCOUNT_JSON
    elif provider == "gemini":
        if GEMINI_OUTPUT_DIM:
            config["output_dimensionality"] = GEMINI_OUTPUT_DIM
        if GOOGLE_API_KEY and not EMBEDDING_API_KEY:
            config["api_key"] = GOOGLE_API_KEY
    elif provider == "lmstudio":
        config["lmstudio_base_url"] = EMBEDDING_LMSTUDIO_BASE_URL
    elif provider == "aws_bedrock":
        if EMBEDDING_AWS_REGION:
            config["aws_region"] = EMBEDDING_AWS_REGION
        if EMBEDDING_AWS_ACCESS_KEY_ID:
            config["aws_access_key_id"] = EMBEDDING_AWS_ACCESS_KEY_ID
        if EMBEDDING_AWS_SECRET_ACCESS_KEY:
            config["aws_secret_access_key"] = EMBEDDING_AWS_SECRET_ACCESS_KEY

    return _compact_dict(config)


def _resolve_embedder_provider() -> str:
    provider = _normalize_embedder_provider(EMBEDDER_PROVIDER)
    if provider and provider != "none":
        return provider
    if EMBEDDING_AZURE_DEPLOYMENT and EMBEDDING_AZURE_ENDPOINT:
        return "azure_openai"
    return "openai"


def _resolve_llm_provider() -> str:
    provider = _normalize_llm_provider(LLM_PROVIDER)
    if provider and provider != "none":
        return provider
    if LLM_AZURE_DEPLOYMENT and LLM_AZURE_ENDPOINT:
        return "azure_openai"
    if VLLM_BASE_URL:
        return "vllm"
    return "openai"


_LLM_PROVIDER = _resolve_llm_provider()
if _LLM_PROVIDER == "azure_openai":
    DEFAULT_CONFIG["llm"] = _azure_llm_config()
elif _LLM_PROVIDER == "vllm":
    DEFAULT_CONFIG["llm"] = _vllm_llm_config()
else:
    DEFAULT_CONFIG["llm"] = {"provider": _LLM_PROVIDER, "config": _build_llm_config(_LLM_PROVIDER)}

_EMBEDDER_PROVIDER = _resolve_embedder_provider()
if _EMBEDDER_PROVIDER == "azure_openai":
    DEFAULT_CONFIG["embedder"] = _azure_embedder_config()
else:
    DEFAULT_CONFIG["embedder"] = {
        "provider": _EMBEDDER_PROVIDER,
        "config": _build_embedder_config(_EMBEDDER_PROVIDER),
    }


MEMORY_INSTANCE = Memory.from_config(DEFAULT_CONFIG)

app = FastAPI(
    title="Mem0 REST APIs",
    description="A REST API for managing and searching memories for your AI Agents and Apps.",
    version="1.0.0",
)


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


@app.post("/configure", summary="Configure Mem0")
def set_config(config: Dict[str, Any]):
    """Set memory configuration."""
    global MEMORY_INSTANCE
    MEMORY_INSTANCE = Memory.from_config(config)
    return {"message": "Configuration set successfully"}


@app.post("/memories", summary="Create memories")
def add_memory(memory_create: MemoryCreate):
    """Store new memories."""
    if not any([memory_create.user_id, memory_create.agent_id, memory_create.run_id]):
        raise HTTPException(status_code=400, detail="At least one identifier (user_id, agent_id, run_id) is required.")

    params = {k: v for k, v in memory_create.model_dump().items() if v is not None and k != "messages"}
    try:
        response = MEMORY_INSTANCE.add(messages=[m.model_dump() for m in memory_create.messages], **params)
        return JSONResponse(content=response)
    except Exception as e:
        logging.exception("Error in add_memory:")  # This will log the full traceback
        raise HTTPException(status_code=500, detail=str(e))


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
