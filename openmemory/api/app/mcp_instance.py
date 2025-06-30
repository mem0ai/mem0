from mcp.server.fastmcp import FastMCP
import logging

# Centralized MCP instance to be imported by tool definitions and the server.
# This avoids circular dependencies.
mcp = FastMCP("Jean Memory")

# Add logging for MCP initialization
logger = logging.getLogger(__name__)
logger.info(f"Initialized MCP server with name: Jean Memory")
logger.info(f"MCP server object: {mcp}")
logger.info(f"MCP internal server: {mcp._mcp_server}") 