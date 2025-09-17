#!/usr/bin/env python3
"""
Production startup script for self-hosted mem0 server
Optimized for AI WhatsApp Assistant integration
"""

import os
import sys
import logging
import asyncio
import signal
from pathlib import Path
from typing import Optional

import uvicorn
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class ProductionServer:
    """Production server manager for mem0."""
    
    def __init__(self):
        self.server: Optional[uvicorn.Server] = None
        self.should_exit = False
        
    def load_environment(self):
        """Load environment configuration."""
        # Load base environment
        load_dotenv()
        
        # Load production environment if available
        prod_env = Path(".env.production")
        if prod_env.exists():
            load_dotenv(prod_env, override=True)
            logger.info("Loaded production environment configuration")
        else:
            logger.warning("Production environment file not found, using defaults")
    
    def validate_configuration(self) -> bool:
        """Validate required configuration."""
        required_vars = [
            "POSTGRES_HOST",
            "POSTGRES_DB", 
            "POSTGRES_USER",
            "POSTGRES_PASSWORD"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.environ.get(var):
                missing_vars.append(var)
        
        if missing_vars:
            logger.error(f"Missing required environment variables: {missing_vars}")
            return False
        
        # Validate LLM configuration
        if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("AZURE_OPENAI_API_KEY"):
            logger.error("Either OPENAI_API_KEY or AZURE_OPENAI_API_KEY must be set")
            return False
        
        logger.info("Configuration validation passed")
        return True
    
    def setup_directories(self):
        """Setup required directories."""
        directories = [
            "/app/data",
            "/app/logs", 
            "/app/backups",
            "/app/history"
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
            logger.info(f"Ensured directory exists: {directory}")
    
    def get_server_config(self) -> dict:
        """Get optimized server configuration."""
        return {
            "app": "main:app",
            "host": os.environ.get("HOST", "0.0.0.0"),
            "port": int(os.environ.get("PORT", "8000")),
            "workers": int(os.environ.get("WORKERS", "4")),
            "reload": os.environ.get("RELOAD", "false").lower() == "true",
            "log_level": os.environ.get("LOG_LEVEL", "info"),
            "access_log": True,
            "use_colors": False,
            "loop": "uvloop",  # Use uvloop for better performance
            "http": "httptools",  # Use httptools for better performance
            "ws": "websockets",
            "lifespan": "on",
            "timeout_keep_alive": 5,
            "timeout_graceful_shutdown": 30,
        }
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            self.should_exit = True
            if self.server:
                self.server.should_exit = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def start_server(self):
        """Start the production server."""
        try:
            config = self.get_server_config()
            logger.info(f"Starting mem0 server with config: {config}")
            
            # Create server instance
            self.server = uvicorn.Server(uvicorn.Config(**config))
            
            # Start server
            await self.server.serve()
            
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            raise
    
    def run(self):
        """Run the production server."""
        try:
            logger.info("Starting mem0 production server...")
            
            # Load environment
            self.load_environment()
            
            # Validate configuration
            if not self.validate_configuration():
                sys.exit(1)
            
            # Setup directories
            self.setup_directories()
            
            # Setup signal handlers
            self.setup_signal_handlers()
            
            # Start server
            asyncio.run(self.start_server())
            
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        except Exception as e:
            logger.error(f"Server error: {e}")
            sys.exit(1)
        finally:
            logger.info("Server shutdown complete")

def main():
    """Main entry point."""
    server = ProductionServer()
    server.run()

if __name__ == "__main__":
    main()
