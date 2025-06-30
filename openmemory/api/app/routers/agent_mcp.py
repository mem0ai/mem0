import logging
from fastapi import APIRouter, Depends, Request, BackgroundTasks

from app.routing.mcp import handle_post_message as mcp_message_handler
from app.models import User
from app.auth import get_current_user

logger = logging.getLogger(__name__)

agent_mcp_router = APIRouter(
    prefix="/agent/v1/mcp",
    tags=["agent-mcp"],
    dependencies=[Depends(get_current_user)]
)

@agent_mcp_router.post("/messages/")
async def handle_agent_message(
    request: Request, 
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user)
):
    """
    Handles authenticated agent requests by forwarding them to the main MCP message handler.
    The user is injected into the request state to be used by the handler.
    """
    request.state.user = user
    return await mcp_message_handler(request, background_tasks)