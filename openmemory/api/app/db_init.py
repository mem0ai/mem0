"""
Database initialization module for Jean Memory
Handles initial setup for local development
"""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from .database import engine, SessionLocal, Base
from .models import User, App
from .settings import config

logger = logging.getLogger(__name__)

def init_database():
    """Initialize the database with required extensions and base data"""
    if config.is_local_development:
        logger.info("Initializing database for local development (using Supabase CLI)")
        
        # For local development with Supabase CLI, the schema is managed by Supabase migrations
        # We only need to ensure extensions are available
        if config.DATABASE_URL.startswith("postgresql"):
            try:
                with engine.connect() as conn:
                    # Enable UUID extension (usually already available in Supabase)
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
                    conn.commit()
                    logger.info("PostgreSQL extensions verified")
            except Exception as e:
                logger.warning(f"Could not verify PostgreSQL extensions: {e}")
        
        # Skip creating default users - we use real Supabase authentication
        logger.info("Local database initialization complete (schema managed by Supabase)")
    else:
        logger.info("Running in production mode - database managed by Alembic migrations")

def create_default_user_and_app():
    """Create default user and app for local development"""
    db = SessionLocal()
    try:
        # Check if default user exists
        # For local development, we'll skip creating default users since we use real Supabase auth
        # This function is kept for compatibility but doesn't create users in local development
        logger.info("Skipping default user creation - using real Supabase authentication")
        return
        
        existing_user = db.query(User).filter(User.user_id == default_user_id).first()
        
        if not existing_user:
            # Create default user
            default_user = User(
                user_id=default_user_id,
                name="Local Developer",
                email="local@example.com"
            )
            db.add(default_user)
            db.commit()
            db.refresh(default_user)
            logger.info(f"Created default user: {default_user_id}")
        else:
            default_user = existing_user
            logger.info(f"Default user already exists: {default_user_id}")
        
        # Check if default app exists
        default_app = db.query(App).filter(
            App.owner_id == default_user.id,
            App.name == "default"
        ).first()
        
        if not default_app:
            # Create default app
            default_app = App(
                owner_id=default_user.id,
                name="default",
                description="Default app for local development",
                is_active=True
            )
            db.add(default_app)
            db.commit()
            logger.info("Created default app for local development")
        else:
            logger.info("Default app already exists")
            
    except Exception as e:
        logger.error(f"Error creating default user and app: {e}")
        db.rollback()
    finally:
        db.close()

def check_database_health():
    """Check if the database is accessible and properly configured"""
    try:
        db = SessionLocal()
        # Try a simple query
        result = db.execute(text("SELECT 1"))
        result.fetchone()
        db.close()
        logger.info("Database health check passed")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False 