"""
Configuration module for OpenMemory API
Handles environment detection and configuration for local vs production
Updated to work with Supabase CLI for local development
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Central configuration class for the application"""
    
    def __init__(self):
        # Supabase configuration (always required now)
        self.SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        self.SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY") 
        self.SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
        
        # Detect if we're using local Supabase CLI
        self.IS_LOCAL_SUPABASE = bool(
            self.SUPABASE_URL and "127.0.0.1:54321" in self.SUPABASE_URL
        )
        
        # Database configuration - use Supabase local DB in development
        if self.IS_LOCAL_SUPABASE:
            # Local Supabase PostgreSQL connection
            self.DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:54322/postgres")
        else:
            # Production database
            self.DATABASE_URL = os.getenv("DATABASE_URL")
        
        # Qdrant configuration (still external service)
        self.QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
        self.QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
        self.QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
        self.QDRANT_COLLECTION_NAME = os.getenv("MAIN_QDRANT_COLLECTION_NAME", "openmemory_dev" if self.IS_LOCAL_SUPABASE else "openmemory_prod")
        
        # OpenAI configuration
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
        self.OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.EMBEDDER_PROVIDER = os.getenv("EMBEDDER_PROVIDER", "openai")
        self.EMBEDDER_MODEL = os.getenv("EMBEDDER_MODEL", "text-embedding-3-small")
        
        # Other API keys
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        self.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
        self.APIFY_TOKEN = os.getenv("APIFY_TOKEN")
        
        # Application settings
        self.APP_NAME = "OpenMemory"
        self.API_VERSION = "1.0.0"
        self.DEBUG = os.getenv("DEBUG", "false").lower() == "true"
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        
        # Development settings
        self.PYTHONUNBUFFERED = os.getenv("PYTHONUNBUFFERED", "1")
    
    @property
    def is_local_development(self) -> bool:
        """Check if we're running with local Supabase CLI"""
        return self.IS_LOCAL_SUPABASE
    
    @property
    def qdrant_url(self) -> str:
        """Get the full Qdrant URL"""
        if self.QDRANT_HOST == "localhost":
            return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"
        else:
            # For cloud Qdrant, use HTTPS
            return f"https://{self.QDRANT_HOST}:{self.QDRANT_PORT}"
    
    @property
    def environment_name(self) -> str:
        """Get a human-readable environment name"""
        return "Local Development" if self.is_local_development else "Production"
    
    def validate(self):
        """Validate the configuration"""
        errors = []
        
        # Always required
        if not self.DATABASE_URL:
            errors.append("DATABASE_URL is required")
        
        if not self.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY is required")
        
        # Supabase is always required now (local or production)
        if not self.SUPABASE_URL:
            errors.append("SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL is required")
        if not self.SUPABASE_ANON_KEY:
            errors.append("SUPABASE_ANON_KEY or NEXT_PUBLIC_SUPABASE_ANON_KEY is required")
        
        # Service key required for some operations
        if not self.SUPABASE_SERVICE_KEY:
            errors.append("SUPABASE_SERVICE_KEY is required for backend operations")
        
        # Qdrant validation
        if self.QDRANT_HOST != "localhost" and not self.QDRANT_API_KEY:
            errors.append("QDRANT_API_KEY is required for cloud Qdrant")
        
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
        return True
    
    def log_configuration(self):
        """Log the current configuration (safely, without secrets)"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Configuration loaded for {self.environment_name}")
        logger.info(f"Database: {'Local PostgreSQL' if self.is_local_development else 'Production PostgreSQL'}")
        logger.info(f"Supabase: {'Local CLI' if self.is_local_development else 'Cloud'}")
        logger.info(f"Qdrant: {self.QDRANT_HOST}:{self.QDRANT_PORT}")
        logger.info(f"Collection: {self.QDRANT_COLLECTION_NAME}")
        logger.info(f"LLM Provider: {self.LLM_PROVIDER}")
        logger.info(f"Debug Mode: {self.DEBUG}")

# Create a singleton instance
config = Config()

# Validate on import (can be disabled for testing)
if os.getenv("SKIP_CONFIG_VALIDATION") != "true":
    try:
        config.validate()
        config.log_configuration()
    except ValueError as e:
        print(f"Warning: {e}")
        print(f"Environment: {config.environment_name}")
        if config.is_local_development:
            print("💡 Tip: Make sure you've run 'supabase start' and copied the values to .env.local")