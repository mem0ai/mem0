"""
pgvector Connection Utility - Phase 2: Infrastructure Setup

Simple utility to test and validate pgvector connectivity and extension availability.
This is part of the safe migration strategy to ensure pgvector is accessible
before implementing the full unified memory system.

Usage:
    from app.utils.pgvector_connection import test_pgvector_connection
    success, info = test_pgvector_connection()
"""

import logging
from typing import Tuple, Dict, Any, Optional
import os

logger = logging.getLogger(__name__)

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    logger.warning("psycopg2 not available. Install with: pip install psycopg2-binary")
    PSYCOPG2_AVAILABLE = False


def get_pgvector_connection_info() -> Dict[str, str]:
    """
    Get pgvector connection information from environment variables.
    
    Returns:
        Dictionary with connection parameters
    """
    from app.settings import config
    
    return {
        "host": config.PGVECTOR_HOST,
        "port": str(config.PGVECTOR_PORT),
        "database": config.PGVECTOR_DATABASE,
        "user": config.PGVECTOR_USER,
        "password": config.PGVECTOR_PASSWORD,
        "table_prefix": config.PGVECTOR_TABLE_PREFIX
    }


def get_pgvector_connection_string() -> str:
    """
    Build PostgreSQL connection string for pgvector.
    
    Returns:
        PostgreSQL connection string
    """
    from app.settings import config
    return config.pgvector_connection_string


def test_pgvector_connection(timeout: int = 5) -> Tuple[bool, Dict[str, Any]]:
    """
    Test pgvector database connection and extension availability.
    
    Args:
        timeout: Connection timeout in seconds
        
    Returns:
        Tuple of (success: bool, info: dict)
    """
    if not PSYCOPG2_AVAILABLE:
        return False, {
            "error": "psycopg2 not installed",
            "message": "Install with: pip install psycopg2-binary",
            "type": "dependency_missing"
        }
    
    try:
        conn_info = get_pgvector_connection_info()
        
        # Validate required parameters
        if not all([conn_info["host"], conn_info["port"], conn_info["database"], 
                   conn_info["user"], conn_info["password"]]):
            return False, {
                "error": "Missing pgvector credentials",
                "message": "PGVECTOR_HOST, PGVECTOR_PORT, PGVECTOR_DATABASE, PGVECTOR_USER, and PGVECTOR_PASSWORD must be set",
                "type": "configuration_error"
            }
        
        # Test connection
        connection = psycopg2.connect(
            host=conn_info["host"],
            port=conn_info["port"],
            database=conn_info["database"],
            user=conn_info["user"],
            password=conn_info["password"],
            cursor_factory=RealDictCursor,
            connect_timeout=timeout
        )
        
        with connection.cursor() as cursor:
            # Test 1: Basic connection
            cursor.execute("SELECT version() AS pg_version")
            version_result = cursor.fetchone()
            
            if not version_result:
                return False, {
                    "error": "No response from PostgreSQL",
                    "type": "connection_error"
                }
            
            # Test 2: Check if pgvector extension exists (but don't require it)
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM pg_available_extensions 
                    WHERE name = 'vector'
                ) AS extension_available
            """)
            extension_check = cursor.fetchone()
            
            # Test 3: Check if pgvector extension is installed
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM pg_extension 
                    WHERE extname = 'vector'
                ) AS extension_installed
            """)
            installation_check = cursor.fetchone()
            
            success_info = {
                "message": "pgvector connection successful!",
                "pg_version": version_result["pg_version"],
                "host": conn_info["host"],
                "port": conn_info["port"],
                "database": conn_info["database"],
                "table_prefix": conn_info["table_prefix"],
                "extension_available": extension_check["extension_available"],
                "extension_installed": installation_check["extension_installed"],
                "type": "success"
            }
            
            logger.info(f"✅ pgvector connection successful: {conn_info['host']}:{conn_info['port']}")
            return True, success_info
        
    except Exception as e:
        error_message = str(e)
        error_type = "connection_error"
        
        # Classify error types for better debugging
        if "authentication" in error_message.lower():
            error_type = "authentication_error"
        elif "timeout" in error_message.lower():
            error_type = "timeout_error"
        elif "refused" in error_message.lower():
            error_type = "connection_refused"
        elif "does not exist" in error_message.lower():
            error_type = "database_not_found"
        
        logger.error(f"❌ pgvector connection failed: {error_message}")
        return False, {
            "error": error_message,
            "type": error_type,
            "host": conn_info.get("host", "unknown"),
            "port": conn_info.get("port", "unknown"),
            "database": conn_info.get("database", "unknown")
        }
    
    finally:
        try:
            if 'connection' in locals():
                connection.close()
        except:
            pass


def install_pgvector_extension() -> Tuple[bool, Dict[str, Any]]:
    """
    Attempt to install the pgvector extension.
    
    Returns:
        Tuple of (success: bool, info: dict)
    """
    if not PSYCOPG2_AVAILABLE:
        return False, {
            "error": "psycopg2 not installed",
            "type": "dependency_missing"
        }
    
    try:
        conn_info = get_pgvector_connection_info()
        
        connection = psycopg2.connect(
            host=conn_info["host"],
            port=conn_info["port"],
            database=conn_info["database"],
            user=conn_info["user"],
            password=conn_info["password"],
            cursor_factory=RealDictCursor
        )
        
        with connection.cursor() as cursor:
            # Try to create the extension
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            connection.commit()
            
            # Verify installation
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM pg_extension 
                    WHERE extname = 'vector'
                ) AS extension_installed
            """)
            result = cursor.fetchone()
            
            if result["extension_installed"]:
                logger.info("✅ pgvector extension installed successfully")
                return True, {
                    "message": "pgvector extension installed successfully",
                    "type": "success"
                }
            else:
                return False, {
                    "error": "Extension installation failed",
                    "type": "installation_failed"
                }
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"❌ pgvector extension installation failed: {error_message}")
        return False, {
            "error": error_message,
            "type": "installation_error"
        }
    
    finally:
        try:
            if 'connection' in locals():
                connection.close()
        except:
            pass


def is_pgvector_ready() -> bool:
    """
    Quick check if pgvector is ready for use.
    
    Returns:
        True if pgvector is available, configured, and extension is installed
    """
    if not PSYCOPG2_AVAILABLE:
        return False
    
    success, info = test_pgvector_connection()
    if not success:
        return False
    
    return info.get("extension_installed", False)


def get_pgvector_status() -> Dict[str, Any]:
    """
    Get comprehensive pgvector status information.
    
    Returns:
        Dictionary with detailed status information
    """
    conn_info = get_pgvector_connection_info()
    success, result = test_pgvector_connection()
    
    status = {
        "available": PSYCOPG2_AVAILABLE,
        "configured": bool(conn_info["host"] and conn_info["user"] and conn_info["password"]),
        "connected": success,
        "host": conn_info["host"],
        "port": conn_info["port"],
        "database": conn_info["database"],
        "table_prefix": conn_info["table_prefix"],
        "result": result
    }
    
    # Add extension status if connected
    if success and "extension_available" in result:
        status["extension_available"] = result["extension_available"]
        status["extension_installed"] = result["extension_installed"]
    else:
        status["extension_available"] = False
        status["extension_installed"] = False
    
    # Add summary status
    if status["available"] and status["configured"] and status["connected"] and status["extension_installed"]:
        status["overall_status"] = "ready"
    elif not status["available"]:
        status["overall_status"] = "driver_missing"
    elif not status["configured"]:
        status["overall_status"] = "not_configured"
    elif not status["connected"]:
        status["overall_status"] = "connection_failed"
    elif not status["extension_installed"]:
        status["overall_status"] = "extension_not_installed"
    else:
        status["overall_status"] = "unknown"
    
    return status


# Phase 2 validation function
def validate_pgvector_for_phase2() -> Tuple[bool, str]:
    """
    Validate pgvector setup for Phase 2 migration.
    
    Returns:
        Tuple of (is_valid: bool, message: str)
    """
    status = get_pgvector_status()
    
    if status["overall_status"] == "ready":
        return True, "✅ pgvector is ready for Phase 2 migration"
    elif status["overall_status"] == "driver_missing":
        return False, "❌ psycopg2 driver not installed. Run: pip install psycopg2-binary"
    elif status["overall_status"] == "not_configured":
        return False, "❌ pgvector not configured. Set PGVECTOR_* environment variables"
    elif status["overall_status"] == "connection_failed":
        error_msg = status["result"].get("error", "Unknown error")
        return False, f"❌ pgvector connection failed: {error_msg}"
    elif status["overall_status"] == "extension_not_installed":
        return False, "❌ pgvector extension not installed. Run CREATE EXTENSION IF NOT EXISTS vector;"
    else:
        return False, f"❌ pgvector status unknown: {status['overall_status']}"


if __name__ == "__main__":
    # Simple test when run directly
    print("Testing pgvector connection...")
    success, info = test_pgvector_connection()
    
    if success:
        print(f"✅ Success: {info['message']}")
        print(f"   Extension available: {info['extension_available']}")
        print(f"   Extension installed: {info['extension_installed']}")
    else:
        print(f"❌ Failed: {info['error']}") 