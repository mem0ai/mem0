import logging
import json
import asyncio
import datetime
import os
from typing import Dict

from fastapi import APIRouter, Request, Response, BackgroundTasks
from fastapi.responses import JSONResponse

from app.clients import get_client_profile, get_client_name
from app.context import user_id_var, client_name_var, background_tasks_var

logger = logging.getLogger(__name__)

# Log service info on startup to help with debugging
SERVICE_NAME = os.getenv('RENDER_SERVICE_NAME', 'unknown-service')
RENDER_REGION = os.getenv('RENDER_REGION', 'unknown-region')
logger.warning(f"🔧 MCP Router initialized on service: {SERVICE_NAME} in region: {RENDER_REGION}")

mcp_router = APIRouter(prefix="/mcp")

# Global dictionary to manage SSE connections
sse_message_queues: Dict[str, asyncio.Queue] = {}

# Session-based ID mapping for ChatGPT
chatgpt_session_mappings: Dict[str, Dict[str, str]] = {}

async def handle_request_logic(request: Request, body: dict, background_tasks: BackgroundTasks):
    """Unified logic to handle an MCP request, abstracted from the transport."""
    from app.auth import get_user_from_api_key_header

    # 1. Determine Authentication and Client Identity
    api_key_auth_success = await get_user_from_api_key_header(request)
    if api_key_auth_success and hasattr(request.state, 'user') and request.state.user:
        is_api_key_path = True
        user_id_from_header = str(request.state.user.user_id)
        client_name_from_header = request.headers.get("x-client-name", "default_agent_app")
    else:
        is_api_key_path = False
        user_id_from_header = request.headers.get("x-user-id")
        client_name_from_header = request.headers.get("x-client-name")

    if not user_id_from_header or not client_name_from_header:
        return JSONResponse(status_code=400, content={"error": "Missing user authentication details"})

    # 2. Set Context and Get Client Profile
    user_token = user_id_var.set(user_id_from_header)
    client_token = client_name_var.set(client_name_from_header)
    tasks_token = background_tasks_var.set(background_tasks)
    
    request_id = body.get("id") # Get request_id early for error reporting
    
    try:
        client_key = get_client_name(client_name_from_header, is_api_key_path)
        client_profile = get_client_profile(client_key)

        # 3. Process MCP Method
        method_name = body.get("method")
        params = body.get("params", {})

        logger.info(f"Handling MCP method '{method_name}' for client '{client_key}'")

        if method_name == "initialize":
            client_version = params.get("protocolVersion", "2024-11-05")
            use_annotations = client_version == "2025-03-26"
            protocol_version = "2025-03-26" if use_annotations else "2024-11-05"
            capabilities = {"tools": {"listChanged": False}, "logging": {}, "sampling": {}} if use_annotations else {"tools": {}}
            
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": protocol_version,
                    "capabilities": capabilities,
                    "serverInfo": {"name": "Jean Memory", "version": "1.0.0"}
                },
                "id": request_id
            })

        elif method_name == "tools/list":
            client_version = params.get("protocolVersion", "2024-11-05")
            tools_schema = client_profile.get_tools_schema(include_annotations=(client_version == "2025-03-26"))
            logger.info(f"🔍 TOOLS/LIST DEBUG - Client: {client_key}, Schema: {json.dumps(tools_schema, indent=2)}")
            return JSONResponse(content={"jsonrpc": "2.0", "result": {"tools": tools_schema}, "id": request_id})

        elif method_name == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            try:
                # Use the profile to handle the tool call, which encapsulates client-specific logic
                result = await client_profile.handle_tool_call(tool_name, tool_args, user_id_from_header)
                # Use the profile to format the response
                return JSONResponse(content=client_profile.format_tool_response(result, request_id))
            except Exception as e:
                logger.error(f"Error calling tool '{tool_name}' for client '{client_key}': {e}", exc_info=True)
                return JSONResponse(status_code=500, content={"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}, "id": request_id})

        # Handle other standard MCP methods
        elif method_name in ["notifications/initialized", "notifications/cancelled"]:
            logger.info(f"Received notification '{method_name}' from client '{client_key}'")
            return JSONResponse(content={"status": "acknowledged"})
        elif method_name in ["resources/list", "prompts/list"]:
            return JSONResponse(content={"jsonrpc": "2.0", "result": {method_name.split('/')[0]: []}, "id": request_id})
        elif method_name == "resources/templates/list":
            return JSONResponse(content={"jsonrpc": "2.0", "result": {"templates": []}, "id": request_id})
        else:
            return JSONResponse(status_code=404, content={"error": f"Method '{method_name}' not found"})

    except Exception as e:
        logger.error(f"Error executing MCP method: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        user_id_var.reset(user_token)
        client_name_var.reset(client_token)
        background_tasks_var.reset(tasks_token)


@mcp_router.post("/messages/")
async def handle_post_message(request: Request, background_tasks: BackgroundTasks):
    """
    Handles a single, stateless JSON-RPC message.
    The logic is now delegated to a shared handler function.
    """
    body = await request.json()
    return await handle_request_logic(request, body, background_tasks)


# ===============================================
# V2 ENDPOINTS - DIRECT HTTP TRANSPORT
# ===============================================

@mcp_router.post("/v2/{client_name}/{user_id}")
async def handle_http_v2_transport(client_name: str, user_id: str, request: Request, background_tasks: BackgroundTasks):
    """
    V2 HTTP Transport Endpoint - Direct backend routing (no Cloudflare proxy)
    
    This endpoint supports HTTP transport with supergateway --stdio flag.
    URL format: https://jean-memory-api-virginia.onrender.com/mcp/v2/{client_name}/{user_id}
    
    Features:
    - Direct connection to backend (no Cloudflare Worker)
    - 50-75% faster performance
    - Better debugging and logging
    - Simplified infrastructure
    - Transport auto-detection
    """
    try:
        # Set headers for context (similar to Cloudflare Worker)
        request.headers.__dict__['_list'].append((b'x-user-id', user_id.encode()))
        request.headers.__dict__['_list'].append((b'x-client-name', client_name.encode()))
        
        body = await request.json()
        method = body.get('method')
        logger.warning(f"🚀 HTTP v2 Transport: {client_name}/{user_id} - Method: {method} - Service: {SERVICE_NAME} ({RENDER_REGION})")
        
        # Use the same unified logic as SSE transport
        response = await handle_request_logic(request, body, background_tasks)
        
        # For HTTP transport, return JSON-RPC response directly (no SSE queue)
        logger.warning(f"✅ HTTP v2 Response: {client_name}/{user_id} - Status: {response.status_code} - Service: {SERVICE_NAME}")
        return response
        
    except Exception as e:
        logger.error(f"❌ HTTP v2 Transport Error: {client_name}/{user_id} - {e}", exc_info=True)
        request_id = None
        try:
            body = await request.json()
            request_id = body.get("id")
        except:
            pass
        
        return JSONResponse(
            status_code=500,
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
                "id": request_id,
            }
        )


# ===============================================
# LEGACY SSE ENDPOINTS - CLOUDFLARE PROXY
# ===============================================

@mcp_router.get("/{client_name}/sse/{user_id}")
async def handle_sse_connection(client_name: str, user_id: str, request: Request):
    """
    SSE endpoint for supergateway compatibility
    This allows npx supergateway to connect to the local development server
    """
    from fastapi.responses import StreamingResponse
    
    logger.info(f"SSE connection from {client_name} for user {user_id}")
    
    # Create a message queue for this connection
    connection_id = f"{client_name}_{user_id}"
    if connection_id not in sse_message_queues:
        sse_message_queues[connection_id] = asyncio.Queue()
    
    async def event_generator():
        try:
            # Send the endpoint event that supergateway expects
            yield f"event: endpoint\ndata: /mcp/{client_name}/messages/{user_id}\n\n"
            
            # CRITICAL FIX: Send an immediate heartbeat to satisfy impatient clients like ChatGPT
            # and prevent the connection from being dropped before the first message.
            yield f"event: heartbeat\ndata: {json.dumps({'timestamp': datetime.datetime.now(datetime.UTC).isoformat()})}\n\n"

            # Main event loop
            while True:
                try:
                    # Check for messages with timeout
                    message = await asyncio.wait_for(
                        sse_message_queues[connection_id].get(), 
                        timeout=1.0
                    )
                    # Send the message through SSE
                    yield f"data: {json.dumps(message)}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat when no messages
                    yield f"event: heartbeat\ndata: {json.dumps({'timestamp': datetime.datetime.now(datetime.UTC).isoformat()})}\n\n"
                    
        except asyncio.CancelledError:
            logger.info(f"SSE connection closed for {client_name}/{user_id}")
            # Clean up the message queue
            if connection_id in sse_message_queues:
                del sse_message_queues[connection_id]
            return
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        },
    )

@mcp_router.post("/{client_name}/messages/{user_id}")
async def handle_sse_messages(client_name: str, user_id: str, request: Request, background_tasks: BackgroundTasks):
    """
    Messages endpoint for supergateway compatibility
    This handles the actual MCP tool calls from supergateway
    """
    try:
        body = await request.json()
        
        # This function will return a JSONResponse object
        response = await handle_request_logic(request, body, background_tasks)
        response_payload = json.loads(response.body)

        # For Cursor, return JSON-RPC directly instead of SSE
        if client_name == "cursor":
            return response

        connection_id = f"{client_name}_{user_id}"
        if connection_id in sse_message_queues:
            await sse_message_queues[connection_id].put(response_payload)
            # CRITICAL FIX: Immediately send a heartbeat after the message to keep the connection alive.
            # In an async queue, we send the dict and the generator formats it
            await sse_message_queues[connection_id].put({'event': 'heartbeat', 'data': {'timestamp': datetime.datetime.now(datetime.UTC).isoformat()}})
            return Response(status_code=204)
        else:
            # No active SSE connection, so return the full payload directly.
            return response
    
    except Exception as e:
        logger.error(f"Error in SSE messages handler: {e}", exc_info=True)
        request_id = None
        try:
            body = await request.json()
            request_id = body.get("id")
        except:
            pass
        
        response_payload = {
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
            "id": request_id,
        }
        
        if client_name == "cursor":
            return JSONResponse(content=response_payload, status_code=500)

        connection_id = f"{client_name}_{user_id}"
        if connection_id in sse_message_queues:
            await sse_message_queues[connection_id].put(response_payload)
            return Response(status_code=204)
        else:
            return JSONResponse(content=response_payload, status_code=500)