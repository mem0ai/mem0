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

# Import our existing MCP tools
try:
    from app.mcp_server import add_memories, search_memory, list_memories, user_id_var, client_name_var
    from app.database import SessionLocal
    from app.utils.db import get_or_create_user
    logger.info("Successfully imported MCP tools")
except ImportError as e:
    logger.error(f"Failed to import MCP tools: {e}")
    sys.exit(1)

# Create MCP server
server = Server("jean-memory-local")

# Set up context variables for the local user
DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_CLIENT_NAME = "claude"

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="add_memories",
            description="Add new memories to the user's memory",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to add to memory"
                    }
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="search_memory",
            description="Search the user's memory for memories that match the query",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (optional)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="list_memories",
            description="List all memories in the user's memory",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of memories to return (optional)",
                        "default": 10
                    }
                },
                "required": []
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Call a tool with the given arguments"""
    # Set context variables for all tool calls
    user_token = user_id_var.set(DEFAULT_USER_ID)
    client_token = client_name_var.set(DEFAULT_CLIENT_NAME)
    
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
        
        # Call the appropriate tool
        if name == "add_memories":
            result = await add_memories(arguments["text"])
        elif name == "search_memory":
            result = await search_memory(arguments["query"], arguments.get("limit"))
        elif name == "list_memories":
            result = await list_memories(arguments.get("limit"))
        else:
            result = f"Unknown tool: {name}"
        
        return [TextContent(type="text", text=str(result))]
    
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        return [TextContent(type="text", text=f"Error: {e}")]
    
    finally:
        # Clean up context variables
        try:
            user_id_var.reset(user_token)
            client_name_var.reset(client_token)
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