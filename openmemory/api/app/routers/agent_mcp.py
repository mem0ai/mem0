import logging
import json
from fastapi import APIRouter, Depends, Request, Header
from fastapi.responses import JSONResponse
from typing import Optional

from app.mcp_server import tool_registry, user_id_var, client_name_var
from app.models import User
from app.auth import get_current_user

logger = logging.getLogger(__name__)

# Create a new router for authenticated agent access
agent_mcp_router = APIRouter(
    prefix="/agent/v1/mcp",
    tags=["agent-mcp"],
    dependencies=[Depends(get_current_user)]
)

@agent_mcp_router.post("/messages/")
async def handle_agent_post_message(
    request: Request, 
    user: User = Depends(get_current_user),
    x_client_name: Optional[str] = Header("default_agent_app", alias="X-Client-Name")
):
    """
    Handles a single, stateless JSON-RPC message from an authenticated agent.
    This endpoint runs the requested tool and returns the result immediately.
    Authenticates using either Supabase JWT or a Jean API Key.
    """
    user_id_from_auth = str(user.user_id)
    client_name_from_header = x_client_name
    
    if not user_id_from_auth or not client_name_from_header:
        return JSONResponse(status_code=400, content={"error": "Missing user authentication or X-Client-Name header"})
            
    user_token = user_id_var.set(user_id_from_auth)
    client_token = client_name_var.set(client_name_from_header)
    
    try:
        body = await request.json()
        method_name = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")

        logger.info(f"Handling Agent MCP method '{method_name}' for user '{user_id_from_auth}' with params: {params}")

        tool_function = tool_registry.get(method_name)
        if not tool_function:
            return JSONResponse(status_code=404, content={"error": f"Method '{method_name}' not found"})
        
        result = await tool_function(**params)

        response_payload = {
            "jsonrpc": "2.0",
            "result": result,
            "id": request_id
        }
        return JSONResponse(content=response_payload)

    except Exception as e:
        logger.error(f"Error executing tool via agent endpoint: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        user_id_var.reset(user_token)
        client_name_var.reset(client_token) 