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
        logger.info("Initializing database for local development")
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        # Initialize PostgreSQL extensions if using PostgreSQL
        if config.DATABASE_URL.startswith("postgresql"):
            try:
                with engine.connect() as conn:
                    # Enable UUID extension
                    conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
                    conn.commit()
                    logger.info("PostgreSQL extensions initialized")
            except Exception as e:
                logger.warning(f"Could not create PostgreSQL extensions: {e}")
        
        # Create default user and app for local development
        create_default_user_and_app()
    else:
        logger.info("Running in production mode - skipping local database initialization")

def create_default_user_and_app():
    """Create default user and app for local development"""
    db = SessionLocal()
    try:
        # Check if default user exists
        default_user_id = config.get_default_user_id()
        if not default_user_id:
            logger.warning("No default user ID configured for local development")
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