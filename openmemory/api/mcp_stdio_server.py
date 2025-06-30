#!/usr/bin/env python3
"""
Stdio MCP Server for Local Development
This allows Claude to connect directly via stdio without needing SSE/HTTP
"""
import asyncio
import os
import sys
import json
import logging
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

# Set environment variables for local development
os.environ.setdefault('USER_ID', '00000000-0000-0000-0000-000000000001')
os.environ.setdefault('DATABASE_URL', 'postgresql://jean_memory:memory_password@localhost:5432/jean_memory_db')
os.environ.setdefault('QDRANT_HOST', 'localhost')
os.environ.setdefault('QDRANT_PORT', '6333')
os.environ.setdefault('QDRANT_API_KEY', '')
os.environ.setdefault('MAIN_QDRANT_COLLECTION_NAME', 'jonathans_memory_main')
os.environ.setdefault('LLM_PROVIDER', 'openai')
os.environ.setdefault('OPENAI_MODEL', 'gpt-4o-mini')
os.environ.setdefault('EMBEDDER_PROVIDER', 'openai')
os.environ.setdefault('EMBEDDER_MODEL', 'text-embedding-3-small')
os.environ.setdefault('SUPABASE_URL', 'http://localhost:8000')
os.environ.setdefault('SUPABASE_ANON_KEY', 'local-dev-anon-key')
os.environ.setdefault('SUPABASE_SERVICE_KEY', 'local-dev-service-key')
os.environ.setdefault('LOG_LEVEL', 'INFO')

# Configure logging to stderr so it doesn't interfere with stdio
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Import MCP components after setting env vars
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Import our new refactored components
try:
    from app.clients import get_client_profile
    from app.tool_registry import tool_registry
    from app.database import SessionLocal
    from app.utils.db import get_or_create_user
    from app.mcp_server import user_id_var, client_name_var, background_tasks_var
    from fastapi import BackgroundTasks
    logger.info("Successfully imported MCP components")
except ImportError as e:
    logger.error(f"Failed to import MCP tools: {e}")
    sys.exit(1)

# Create MCP server
server = Server("jean-memory-local")

# Set up context variables for the local user
DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_CLIENT_NAME = "claude"

# Get the client profile for the local dev environment
local_client_profile = get_client_profile(DEFAULT_CLIENT_NAME)

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools using the client profile."""
    schema = local_client_profile.get_tools_schema()
    # Convert to MCP Tool objects
    return [Tool.model_validate(tool_schema) for tool_schema in schema]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Call a tool with the given arguments"""
    # Set context variables for all tool calls
    user_token = user_id_var.set(DEFAULT_USER_ID)
    client_token = client_name_var.set(DEFAULT_CLIENT_NAME)
    # Stdio server doesn't have a real background task queue, so we create a dummy one
    tasks_token = background_tasks_var.set(BackgroundTasks())

    try:
        # Ensure user exists in database
        try:
            db = SessionLocal()
            user = get_or_create_user(db, supabase_user_id=DEFAULT_USER_ID, email="local@dev.com")
            db.close()
            logger.info(f"User ready: {user.id}")
        except Exception as e:
            logger.error(f"Database setup error: {e}")
            return [TextContent(type="text", text=f"Database error: {e}")]

        # Use the client profile to handle the tool call
        result = await local_client_profile.handle_tool_call(
            tool_name=name,
            tool_args=arguments,
            user_id=DEFAULT_USER_ID
        )

        # The result from handle_tool_call is the raw return value of the function.
        # We need to wrap it in the TextContent type for the stdio server.
        return [TextContent(type="text", text=str(result))]

    except Exception as e:
        logger.error(f"Tool execution error: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {e}")]

    finally:
        # Clean up context variables
        try:
            user_id_var.reset(user_token)
            client_name_var.reset(client_token)
            background_tasks_var.reset(tasks_token)
        except:
            pass

async def main():
    """Main entry point for the stdio server"""
    logger.info("Starting Jean Memory stdio MCP server...")
    
    # Test database connection
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        logger.info("Database connection successful")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        sys.exit(1)
    
    # Run the stdio server
    await stdio_server(server)

if __name__ == "__main__":
    asyncio.run(main()) 