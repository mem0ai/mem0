"""
Configuration module for Jean Memory API
Handles environment detection and configuration for local vs production
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Central configuration class for the application"""
    
    def __init__(self):
        # Detect if we're in local development mode
        self.USER_ID = os.getenv("USER_ID")
        self.IS_LOCAL_DEV = bool(self.USER_ID)
        
        # Database configuration
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./openmemory.db")
        
        # Supabase configuration (may be dummy values in local dev)
        self.SUPABASE_URL = os.getenv("SUPABASE_URL")
        self.SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
        self.SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
        
        # Qdrant configuration
        self.QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
        self.QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
        self.QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
        self.QDRANT_COLLECTION_NAME = os.getenv("MAIN_QDRANT_COLLECTION_NAME", "jonathans_memory_main")
        
        # OpenAI configuration
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        
        # Other API keys
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        self.ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
        
        # Application settings
        self.APP_NAME = "Jean Memory"
        self.API_VERSION = "1.0.0"
        self.DEBUG = os.getenv("DEBUG", "false").lower() == "true"
        
    @property
    def is_local_development(self) -> bool:
        """Check if we're running in local development mode"""
        return self.IS_LOCAL_DEV
    
    @property
    def requires_supabase_auth(self) -> bool:
        """Check if Supabase authentication is required"""
        return not self.IS_LOCAL_DEV
    
    @property
    def qdrant_url(self) -> str:
        """Get the full Qdrant URL"""
        if self.QDRANT_HOST == "localhost":
            return f"http://{self.QDRANT_HOST}:{self.QDRANT_PORT}"
        else:
            # For cloud Qdrant
            return f"https://{self.QDRANT_HOST}:{self.QDRANT_PORT}"
    
    def get_default_user_id(self) -> Optional[str]:
        """Get the default user ID for local development"""
        return self.USER_ID if self.is_local_development else None
    
    def validate(self):
        """Validate the configuration"""
        errors = []
        
        # Always required
        if not self.DATABASE_URL:
            errors.append("DATABASE_URL is required")
        
        if not self.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY is required")
        
        # Required for production
        if not self.is_local_development:
            if not self.SUPABASE_URL:
                errors.append("SUPABASE_URL is required in production")
            if not self.SUPABASE_ANON_KEY:
                errors.append("SUPABASE_ANON_KEY is required in production")
        
        # Qdrant validation
        if self.QDRANT_HOST != "localhost" and not self.QDRANT_API_KEY:
            errors.append("QDRANT_API_KEY is required for cloud Qdrant")
        
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
        return True

# Create a singleton instance
config = Config()

# Validate on import (can be disabled for testing)
if os.getenv("SKIP_CONFIG_VALIDATION") != "true":
    try:
        config.validate()
    except ValueError as e:
        print(f"Warning: {e}")