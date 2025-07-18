from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field

from api.app.utils.memory import get_memory_instance
from api.app.config import USER_ID


def get_current_user() -> str:
    return USER_ID


class SearchMemoryArgs(BaseModel):
    query: str
    top_k: Optional[int] = Field(default=10, alias="topK")
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    filters: Optional[Dict[str, Any]] = None
    project_id: Optional[str] = Field(default=None, alias="projectId")
    org_id: Optional[str] = Field(default=None, alias="orgId")


async def search_memory_handler(arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
    args = SearchMemoryArgs(**arguments)
    current_user = get_current_user()

    memory_client = get_memory_instance()

    search_params = {
        "query": args.query,
        "user_id": current_user,
    }
    if args.top_k is not None:
        search_params["limit"] = args.top_k
    if args.threshold is not None:
        search_params["threshold"] = args.threshold
    if args.filters is not None:
        search_params["filters"] = args.filters
    if args.project_id is not None:
        search_params["project_id"] = args.project_id
    if args.org_id is not None:
        search_params["org_id"] = args.org_id

    results = memory_client.search(**search_params)
    return results.get("results", [])


class AddMemoriesArgs(BaseModel):
    messages: List[str]
    metadata: Optional[Dict[str, Any]] = None
    project_id: Optional[str] = Field(default=None, alias="projectId")
    org_id: Optional[str] = Field(default=None, alias="orgId")


async def add_memories_handler(arguments: Dict[str, Any]) -> Dict[str, Any]:
    args = AddMemoriesArgs(**arguments)
    current_user = get_current_user()

    memory_client = get_memory_instance()

    add_params = {
        "messages": [{"role": "user", "content": m} for m in args.messages],
        "user_id": current_user,
    }
    if args.metadata is not None:
        add_params["metadata"] = args.metadata
    if args.project_id is not None:
        add_params["project_id"] = args.project_id
    if args.org_id is not None:
        add_params["org_id"] = args.org_id

    result = memory_client.add(**add_params)
    return {"success": True, "memory_ids": result}


search_memory_tool = {
    "name": "search_memory",
    "description": "Search through stored memories using semantic similarity with advanced filtering options",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Natural language search query"},
            "topK": {"type": "integer", "description": "Maximum number of results to return (default: 10)", "minimum": 1, "maximum": 100, "default": 10},
            "threshold": {"type": "number", "description": "Minimum similarity score (0.0-1.0)", "minimum": 0.0, "maximum": 1.0},
            "filters": {"type": "object", "description": "Metadata filters for refined search", "additionalProperties": True},
            "projectId": {"type": "string", "description": "Filter by specific project ID"},
            "orgId": {"type": "string", "description": "Filter by specific organization ID"}
        },
        "required": ["query"]
    }
}

add_memories_tool = {
    "name": "add_memories",
    "description": "Store new memories with metadata and organizational context",
    "inputSchema": {
        "type": "object",
        "properties": {
            "messages": {"type": "array", "items": {"type": "string"}, "description": "List of text content to store as memories"},
            "metadata": {"type": "object", "description": "Custom metadata/tags for the memories", "additionalProperties": True},
            "projectId": {"type": "string", "description": "Assign memories to specific project"},
            "orgId": {"type": "string", "description": "Assign memories to specific organization"}
        },
        "required": ["messages"]
    }
}
