import logging
import os
from dotenv import load_dotenv

from fastapi import FastAPI

# Load environment variables at the very top
load_dotenv()

# Set up logging
# The basicConfig should be called only once.
# If your application is started from a different entry point, ensure this is handled there.
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Use force=True if you suspect the config might be set elsewhere
)
logger = logging.getLogger(__name__)

# --- Centralized Imports and Setup ---

# Import the singleton MCP instance.
# This must be done before importing tools so the @mcp.tool decorator works correctly.
from app.mcp_instance import mcp

# Import all tool modules. This action is what triggers the @mcp.tool decorators
# inside those files, registering them with the central `mcp` instance.
import app.tools

# Import the routers that define the API endpoints
from app.routing.mcp import mcp_router
from app.routing.chorus import chorus_router


def setup_mcp_server(app: FastAPI):
    """
    Set up the MCP server with the FastAPI application.
    This function wires together all the components.
    """
    # The routers contain all the endpoint logic.
    app.include_router(mcp_router)
    app.include_router(chorus_router)
    logger.info("MCP server setup complete - included MCP and Chorus routers.")

# This file is now primarily for initialization and setup.
# All tool logic, routing, and client-specific handling
# have been moved to their respective modules.