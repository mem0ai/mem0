import os
from fastapi import FastAPI, HTTPException, Query, Path
from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from mem0 import Memory
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get environment variable values
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Additional environment variables can be loaded here as needed.

# Create a default configuration dictionary using env variables if available
default_config = {}
if OPENAI_API_KEY:
    default_config["llm"] = {
        "provider": "openai",
        "config": {
            "api_key": OPENAI_API_KEY,
            "model": "gpt-4"  # Change model as needed
        }
    }
    default_config["embedder"] = {
        "provider": "openai",
        "config": {
            "api_key": OPENAI_API_KEY,
            "model": "text-embedding-3-small"
        }
    }

# Initialize a global Memory instance using the default configuration (if provided)
if default_config:
    m = Memory.from_config(default_config)
else:
    m = Memory()

app = FastAPI(
    title="Mem0 API",
    description="A REST API to interact with Mem0, supporting operations like add, get, search, update, history, delete and reset.",
    version="1.0.0"
)

# Pydantic models for request and response bodies


class MemoryCreate(BaseModel):
    memory: str = Field(..., description="The memory text to store.")
    user_id: str = Field(..., description="ID of the user.")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata.")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Optional custom configuration for creating the Memory instance.")


class MemoryUpdate(BaseModel):
    memory: str = Field(..., description="The updated memory text.")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Optional custom configuration for creating the Memory instance.")


class SearchRequest(BaseModel):
    query: str = Field(..., description="The search query string.")
    user_id: str = Field(..., description="ID of the user.")
    config: Optional[Dict[str, Any]] = Field(default=None, description="Optional custom configuration for creating the Memory instance.")

# Endpoints

@app.post("/memories", summary="Store a new memory", response_model=Dict[str, Any])
def add_memory(memory_create: MemoryCreate):
    """
    Add a memory for a user.
    Optionally, pass a custom configuration in the request body via the `config` field.
    """
    try:
        # Use custom config if provided, otherwise use the global memory instance
        memory_instance = Memory.from_config(memory_create.config) if memory_create.config else m
        result = memory_instance.add(memory_create.memory, user_id=memory_create.user_id, metadata=memory_create.metadata)
        if 'error' in result:
            raise HTTPException(status_code=400, detail="Error code: 400 - " + str(result))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memories", summary="Get all memories for a user", response_model=Dict[str, Any])
def get_all_memories(user_id: str = Query(..., description="User ID to fetch memories for")):
    """
    Retrieve all memories for a given user.
    """
    try:
        result = m.get_all(user_id=user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memories/{memory_id}", summary="Get a specific memory", response_model=Dict[str, Any])
def get_memory(memory_id: str = Path(..., description="ID of the memory to retrieve")):
    """
    Retrieve a single memory by its ID.
    """
    try:
        result = m.get(memory_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search", summary="Search memories", response_model=Dict[str, Any])
def search_memories(search_req: SearchRequest):
    """
    Search for memories related to a given query.
    Optionally, pass a custom configuration in the request body via the `config` field.
    """
    try:
        memory_instance = Memory.from_config(search_req.config) if search_req.config else m
        result = memory_instance.search(query=search_req.query, user_id=search_req.user_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/memories/{memory_id}", summary="Update a memory", response_model=Dict[str, Any])
def update_memory(
    memory_id: str = Path(..., description="ID of the memory to update"),
    memory_update: MemoryUpdate = ...
):
    """
    Update an existing memory.
    Optionally, pass a custom configuration in the request body via the `config` field.
    """
    try:
        memory_instance = Memory.from_config(memory_update.config) if memory_update.config else m
        result = memory_instance.update(memory_id=memory_id, data=memory_update.memory)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memories/{memory_id}/history", summary="Get memory history", response_model=List[Dict[str, Any]])
def memory_history(memory_id: str = Path(..., description="ID of the memory to retrieve history for")):
    """
    Get the history of changes for a given memory.
    """
    try:
        result = m.history(memory_id=memory_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/memories/{memory_id}", summary="Delete a specific memory", response_model=Dict[str, Any])
def delete_memory(memory_id: str = Path(..., description="ID of the memory to delete")):
    """
    Delete a specific memory by its ID.
    """
    try:
        m.delete(memory_id=memory_id)
        return {"message": "Memory deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/memories", summary="Delete all memories for a user", response_model=Dict[str, Any])
def delete_all_memories(user_id: str = Query(..., description="User ID whose memories will be deleted")):
    """
    Delete all memories for a specified user.
    """
    try:
        m.delete_all(user_id=user_id)
        return {"message": f"All memories for user '{user_id}' have been deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reset", summary="Reset all memories", response_model=Dict[str, Any])
def reset_memory():
    """
    Reset all memories stored in the system.
    """
    try:
        m.reset()
        return {"message": "All memories have been reset"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
