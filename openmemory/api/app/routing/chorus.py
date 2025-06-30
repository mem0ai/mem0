import logging
from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse

# Import the shared request handler
from .mcp import handle_request_logic

logger = logging.getLogger(__name__)

chorus_router = APIRouter(prefix="/mcp/chorus")

@chorus_router.get("/sse/{user_id}")
async def handle_chorus_sse(user_id: str, request: Request):
    """
    Simple SSE endpoint that just provides the messages endpoint
    No heartbeats or streaming - just the endpoint event and done
    """
    async def simple_chorus_sse():
        # Send only the endpoint event - no heartbeats to avoid parsing issues
        yield f"event: endpoint\ndata: /mcp/chorus/messages/{user_id}\n\n"
        # Stream ends here - no infinite loop or heartbeats
    
    return StreamingResponse(
        simple_chorus_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        }
    )

@chorus_router.post("/sse/{user_id}")
async def handle_chorus_sse_post(user_id: str, request: Request, background_tasks: BackgroundTasks):
    """
    Handle POST requests to SSE endpoint - redirect to messages handler
    This supports http-first transport strategy
    """
    return await handle_chorus_messages(user_id, request, background_tasks)

@chorus_router.post("/messages/{user_id}")
async def handle_chorus_messages(user_id: str, request: Request, background_tasks: BackgroundTasks):
    """
    Direct HTTP JSON-RPC endpoint for Chorus - bypasses Worker completely
    Returns JSON-RPC responses directly via HTTP without SSE.
    Delegates all logic to the centralized handler.
    """
    try:
        body = await request.json()
        logger.info(f"Chorus direct HTTP: {body.get('method')} for user {user_id}")
        # This endpoint doesn't go through the API gateway, so is_api_key is false
        # We also pass background_tasks from the endpoint definition
        return await handle_request_logic(request, body, background_tasks)
    except Exception as e:
        logger.error(f"Error in Chorus direct HTTP handler: {e}", exc_info=True)
        request_id = None
        try:
            body = await request.json()
            request_id = body.get("id")
        except:
            pass
        error_response = {
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
            "id": request_id
        }
        logger.info(f"Chorus error response: {error_response}")
        return JSONResponse(status_code=200, content=error_response)  # Return 200 for JSON-RPC errors 