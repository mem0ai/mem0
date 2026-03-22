"""
HTTP Streamable Transport for MCP (Model Context Protocol)

Converts the stdio-based MCP server to HTTP streamable transport
for deployment on Fly.io. Supports Server-Sent Events (SSE) for
real-time streaming responses.

Features:
- HTTP/2 support for multiplexed requests
- Server-Sent Events for streaming
- Request/response correlation
- Graceful error handling
- Connection keep-alive
"""

import os
import json
import asyncio
import uuid
from typing import Optional, AsyncGenerator, Dict, Any
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import structlog

from auth_middleware import get_current_user, auth_router, SecurityHeadersMiddleware

logger = structlog.get_logger()

# Configuration
MCP_HTTP_STREAMABLE = os.environ.get("MCP_HTTP_STREAMABLE", "true").lower() == "true"
MAX_STREAMING_DURATION = int(os.environ.get("MAX_STREAMING_DURATION", "300"))  # 5 minutes


class MCPSession:
    """Manages an MCP session over HTTP"""

    def __init__(self, session_id: str, user_id: str):
        self.session_id = session_id
        self.user_id = user_id
        self.created_at = datetime.now(timezone.utc)
        self.last_activity = self.created_at
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.response_futures: Dict[str, asyncio.Future] = {}
        self._closed = False

    async def send_message(self, message: dict) -> Optional[dict]:
        """Send a message and optionally wait for response"""
        message_id = message.get("id") or str(uuid.uuid4())
        message["id"] = message_id

        # Create future for response if this is a request
        if message.get("method"):
            future = asyncio.get_event_loop().create_future()
            self.response_futures[message_id] = future

        await self.message_queue.put(message)
        self.last_activity = datetime.now(timezone.utc)

        # Wait for response if applicable
        if message.get("method"):
            try:
                response = await asyncio.wait_for(
                    future,
                    timeout=MAX_STREAMING_DURATION
                )
                return response
            except asyncio.TimeoutError:
                del self.response_futures[message_id]
                raise HTTPException(status_code=504, detail="Request timeout")

        return None

    async def receive_response(self, response: dict):
        """Receive a response for a pending request"""
        message_id = response.get("id")
        if message_id and message_id in self.response_futures:
            self.response_futures[message_id].set_result(response)
            del self.response_futures[message_id]

    async def stream_messages(self) -> AsyncGenerator[str, None]:
        """Stream messages as SSE events"""
        while not self._closed:
            try:
                message = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=30  # Send keepalive every 30s
                )
                yield f"data: {json.dumps(message)}\n\n"
            except asyncio.TimeoutError:
                # Send keepalive
                yield ": keepalive\n\n"

    def close(self):
        """Close the session"""
        self._closed = True
        # Cancel any pending futures
        for future in self.response_futures.values():
            if not future.done():
                future.cancel()


# Session storage
sessions: Dict[str, MCPSession] = {}


def get_or_create_session(session_id: str, user_id: str) -> MCPSession:
    """Get existing session or create new one"""
    if session_id not in sessions:
        sessions[session_id] = MCPSession(session_id, user_id)
        logger.info("Created new MCP session", session_id=session_id, user_id=user_id)
    return sessions[session_id]


def cleanup_old_sessions(max_age_seconds: int = 3600):
    """Clean up sessions older than max_age"""
    now = datetime.now(timezone.utc)
    expired = []
    for session_id, session in sessions.items():
        age = (now - session.last_activity).total_seconds()
        if age > max_age_seconds:
            expired.append(session_id)

    for session_id in expired:
        sessions[session_id].close()
        del sessions[session_id]
        logger.info("Cleaned up expired session", session_id=session_id)


# Create the FastAPI transport app
def create_http_transport_routes(app: FastAPI, mcp_handler):
    """
    Add HTTP transport routes to the FastAPI app

    Args:
        app: FastAPI application
        mcp_handler: The MCP message handler function
    """

    @app.post("/mcp/message")
    async def mcp_message(
        request: Request,
        current_user: dict = Depends(get_current_user)
    ):
        """
        Send a message to the MCP server

        This is the main endpoint for MCP communication over HTTP.
        Messages follow the JSON-RPC 2.0 format used by MCP.
        """
        try:
            body = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        user_id = current_user.get("user_id")
        session_id = request.headers.get("X-MCP-Session-ID", str(uuid.uuid4()))

        logger.info(
            "MCP message received",
            method=body.get("method"),
            session_id=session_id,
            user_id=user_id
        )

        # Process through MCP handler
        try:
            response = await mcp_handler(body, user_id=user_id)
            return response
        except Exception as e:
            logger.error("MCP handler error", error=str(e))
            return {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }

    @app.get("/mcp/stream")
    async def mcp_stream(
        request: Request,
        current_user: dict = Depends(get_current_user)
    ):
        """
        Server-Sent Events stream for MCP notifications and responses

        Use this for real-time streaming of MCP events.
        """
        user_id = current_user.get("user_id")
        session_id = request.headers.get("X-MCP-Session-ID", str(uuid.uuid4()))

        session = get_or_create_session(session_id, user_id)

        async def event_generator():
            # Send initial connection event
            yield {
                "event": "connected",
                "data": json.dumps({
                    "session_id": session_id,
                    "user_id": user_id
                })
            }

            try:
                async for message in session.stream_messages():
                    yield {"data": message}
            except asyncio.CancelledError:
                session.close()
                logger.info("SSE stream cancelled", session_id=session_id)

        return EventSourceResponse(
            event_generator(),
            headers={
                "X-MCP-Session-ID": session_id,
                "Cache-Control": "no-cache",
            }
        )

    @app.post("/mcp/batch")
    async def mcp_batch(
        request: Request,
        current_user: dict = Depends(get_current_user)
    ):
        """
        Send multiple MCP messages in a batch

        Useful for reducing round trips when sending multiple requests.
        """
        try:
            messages = await request.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON")

        if not isinstance(messages, list):
            raise HTTPException(status_code=400, detail="Expected array of messages")

        user_id = current_user.get("user_id")
        responses = []

        for msg in messages:
            try:
                response = await mcp_handler(msg, user_id=user_id)
                responses.append(response)
            except Exception as e:
                responses.append({
                    "jsonrpc": "2.0",
                    "id": msg.get("id"),
                    "error": {
                        "code": -32603,
                        "message": str(e)
                    }
                })

        return responses

    @app.websocket("/mcp/ws")
    async def mcp_websocket(websocket):
        """
        WebSocket endpoint for bidirectional MCP communication

        Alternative to SSE for environments that support WebSocket.
        """
        from fastapi import WebSocket
        await websocket.accept()

        # TODO: Add authentication for WebSocket
        session_id = str(uuid.uuid4())
        user_id = "websocket_user"  # Should be extracted from auth

        logger.info("WebSocket connected", session_id=session_id)

        try:
            while True:
                data = await websocket.receive_json()
                response = await mcp_handler(data, user_id=user_id)
                await websocket.send_json(response)
        except Exception as e:
            logger.error("WebSocket error", error=str(e))
        finally:
            logger.info("WebSocket disconnected", session_id=session_id)


async def periodic_session_cleanup():
    """Background task to clean up expired sessions"""
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        cleanup_old_sessions()


def setup_http_transport(app: FastAPI, mcp_handler):
    """
    Complete setup for HTTP transport

    Args:
        app: FastAPI application
        mcp_handler: The MCP message handler function
    """
    # Add auth routes
    app.include_router(auth_router)

    # Add auth middleware
    app.add_middleware(AuthMiddleware)

    # Add MCP routes
    create_http_transport_routes(app, mcp_handler)

    # Start background cleanup task
    @app.on_event("startup")
    async def start_cleanup():
        asyncio.create_task(periodic_session_cleanup())

    logger.info("HTTP transport setup complete")
