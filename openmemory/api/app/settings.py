"""
Configuration module for OpenMemory API
Handles environment detection and configuration for local vs production
Updated to work with Supabase CLI for local development
"""
import os
from typing import Optional
from dotenv import load_dotenv
import pathlib

# Determine the correct environment file path
# Priority: .env.local > api/.env > .env
project_root = pathlib.Path(__file__).parent.parent.parent  # openmemory/
api_dir = pathlib.Path(__file__).parent.parent  # openmemory/api/

# Load environment files in order of precedence
env_files = [
    project_root / ".env.local",  # Local development (highest priority)
    api_dir / ".env",             # API-specific environment
    project_root / ".env",        # Fallback
]

for env_file in env_files:
    if env_file.exists():
        load_dotenv(env_file)
        print(f"Loaded environment from: {env_file}")

class Config:
    """Central configuration class for the application"""
    
    def __init__(self):
        # Explicit production environment detection
        # In production (Render), set ENVIRONMENT=production
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
        self.IS_PRODUCTION = self.ENVIRONMENT == "production"
        
        # Supabase configuration (always required now)
        self.SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        self.SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY") 
        self.SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
        
        # Detect if we're using local Supabase CLI
        self.IS_LOCAL_SUPABASE = bool(
            self.SUPABASE_URL and "127.0.0.1:54321" in self.SUPABASE_URL
        ) and not self.IS_PRODUCTION
        
        # Database configuration
        if self.IS_LOCAL_SUPABASE:
            # Local Supabase PostgreSQL connection
            self.DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:54322/postgres")
        else:
            # Production database
            self.DATABASE_URL = os.getenv("DATABASE_URL")
        
        # Qdrant configuration
        self.QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
        self.QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
        self.QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
        
        # Collection name based on environment
        default_collection = "openmemory_dev" if self.is_local_development else "openmemory_prod"
        self.QDRANT_COLLECTION_NAME = os.getenv("MAIN_QDRANT_COLLECTION_NAME", default_collection)
        
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
        
        # Stripe configuration
        self.STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
        self.STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
        
        # Application settings
        self.APP_NAME = "OpenMemory"
        self.API_VERSION = "1.0.0"
        self.DEBUG = os.getenv("DEBUG", "false").lower() == "true"
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        
        # Development settings
        self.PYTHONUNBUFFERED = os.getenv("PYTHONUNBUFFERED", "1")
        
        # User ID for local development
        self.USER_ID = os.getenv("USER_ID", "00000000-0000-0000-0000-000000000001")
        
    @property
    def is_local_development(self) -> bool:
        """Check if we're running in local development mode"""
        return not self.IS_PRODUCTION and (self.IS_LOCAL_SUPABASE or self.ENVIRONMENT == "development")
    
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
        if self.IS_PRODUCTION:
            return "Production"
        elif self.IS_LOCAL_SUPABASE:
            return "Local Development (Supabase CLI)"
        else:
            return "Development"
    
    def validate(self):
        """Validate the configuration"""
        errors = []
        
        # Always required
        if not self.DATABASE_URL:
            errors.append("DATABASE_URL is required")
        
        if not self.OPENAI_API_KEY or self.OPENAI_API_KEY == "your_openai_api_key_here":
            errors.append("OPENAI_API_KEY is required and must be set to a real key")
        
        # Supabase is always required now (local or production)
        if not self.SUPABASE_URL:
            errors.append("SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL is required")
        if not self.SUPABASE_ANON_KEY or self.SUPABASE_ANON_KEY == "auto-generated-by-setup":
            errors.append("SUPABASE_ANON_KEY or NEXT_PUBLIC_SUPABASE_ANON_KEY is required and must be set to a real key")
        
        # Service key required for some operations
        if not self.SUPABASE_SERVICE_KEY or self.SUPABASE_SERVICE_KEY == "auto-generated-by-setup":
            errors.append("SUPABASE_SERVICE_KEY is required for backend operations and must be set to a real key")
        
        # Qdrant validation
        if self.QDRANT_HOST != "localhost" and not self.QDRANT_API_KEY:
            errors.append("QDRANT_API_KEY is required for cloud Qdrant")
        
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
        return True
    
    @property
    def uses_alembic_migrations(self) -> bool:
        """Check if this environment should use Alembic migrations (production)"""
        return self.IS_PRODUCTION
    
    def log_configuration(self):
        """Log the current configuration (safely, without secrets)"""
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"Configuration loaded for {self.environment_name}")
        logger.info(f"Environment: {self.ENVIRONMENT}")
        logger.info(f"Is Production: {self.IS_PRODUCTION}")
        logger.info(f"Database: {'Local PostgreSQL' if self.is_local_development else 'Production PostgreSQL'}")
        logger.info(f"Supabase: {'Local CLI' if self.IS_LOCAL_SUPABASE else 'Cloud'}")
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
            print("💡 Tip: Make sure you've run the setup script and added your API keys")