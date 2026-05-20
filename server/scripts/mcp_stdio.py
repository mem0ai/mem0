import json
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Literal, Optional

from mcp.server.fastmcp import FastMCP
# Ensure the parent directory is in sys.path so we can import server_state
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from server_state import get_memory_instance

# Initialize FastMCP
mcp = FastMCP("mem0-local")

@mcp.tool()
def add_memory(messages: List[Dict[str, str]], user_id: str, agent_id: Optional[str] = None, run_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
    """Store new memories. Provide a list of messages with 'role' and 'content'."""
    try:
        res = get_memory_instance().add(messages, user_id=user_id, agent_id=agent_id, run_id=run_id, metadata=metadata)
        return json.dumps(res)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def search_memories(query: str, user_id: Optional[str] = None, agent_id: Optional[str] = None, run_id: Optional[str] = None, filters: Optional[Dict[str, Any]] = None, top_k: int = 10) -> str:
    """Search for relevant memories."""
    try:
        # Move entity IDs into filters for search()
        effective_filters = filters or {}
        if user_id: effective_filters["user_id"] = user_id
        if agent_id: effective_filters["agent_id"] = agent_id
        if run_id: effective_filters["run_id"] = run_id

        res = get_memory_instance().search(query, filters=effective_filters, top_k=top_k)
        return json.dumps(res)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_memories(user_id: Optional[str] = None, agent_id: Optional[str] = None, run_id: Optional[str] = None) -> str:
    """List memories for a given user, agent, or run."""
    try:
        # Move entity IDs into filters for get_all()
        filters = {}
        if user_id: filters["user_id"] = user_id
        if agent_id: filters["agent_id"] = agent_id
        if run_id: filters["run_id"] = run_id

        res = get_memory_instance().get_all(filters=filters)
        return json.dumps(res)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_memory(memory_id: str) -> str:
    """Retrieve a specific memory by its ID."""
    try:
        res = get_memory_instance().get(memory_id)
        return json.dumps(res)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def update_memory(memory_id: str, data: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """Update an existing memory's content or metadata."""
    try:
        res = get_memory_instance().update(memory_id, data, metadata=metadata)
        return json.dumps(res)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def delete_memory(memory_id: str) -> str:
    """Delete a specific memory by its ID."""
    try:
        get_memory_instance().delete(memory_id)
        return "Memory deleted successfully"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def delete_all_memories(user_id: Optional[str] = None, agent_id: Optional[str] = None, run_id: Optional[str] = None) -> str:
    """Delete all memories for a given identifier."""
    try:
        # delete_all() supports top-level kwargs
        get_memory_instance().delete_all(user_id=user_id, agent_id=agent_id, run_id=run_id)
        return "Memories deleted successfully"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def list_entities() -> str:
    """List all users, agents, and runs that have stored memories."""
    try:
        SCAN_LIMIT = 10_000
        results = get_memory_instance().vector_store.list(top_k=SCAN_LIMIT)

        # Robustly extract rows from different vector store return formats
        rows = []
        if isinstance(results, tuple):
            rows = results[0]
        elif isinstance(results, list):
            if results and isinstance(results[0], list):
                rows = results[0]
            else:
                rows = results

        payloads = [getattr(row, "payload", None) or {} for row in rows]

        buckets = defaultdict(lambda: {"total_memories": 0})
        for payload in payloads:
            for entity_type, field in [("user", "user_id"), ("agent", "agent_id"), ("run", "run_id")]:
                value = payload.get(field)
                if value:
                    buckets[(entity_type, str(value))]["total_memories"] += 1

        entities = [{"id": eid, "type": etype, **data} for (etype, eid), data in buckets.items()]
        return json.dumps(entities)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def delete_entities(entity_type: str, entity_id: str) -> str:
    """Delete all memories for a specific entity type (user, agent, or run)."""
    try:
        TYPE_TO_FIELD = {"user": "user_id", "agent": "agent_id", "run": "run_id"}
        if entity_type not in TYPE_TO_FIELD:
            return "Error: entity_type must be 'user', 'agent', or 'run'"

        get_memory_instance().delete_all(**{TYPE_TO_FIELD[entity_type]: entity_id})
        return f"Entity {entity_id} ({entity_type}) deleted successfully"
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    # Import main to initialize the Memory instance if needed
    from main import DEFAULT_CONFIG
    from server_state import initialize_state, set_session_factory
    from db import SessionLocal

    set_session_factory(SessionLocal)
    initialize_state(DEFAULT_CONFIG)

    mcp.run()
