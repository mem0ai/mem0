"""
Neo4j Connection Utility - Phase 1: Infrastructure Setup

Simple utility to test and validate Neo4j connectivity.
This is part of the safe migration strategy to ensure Neo4j is accessible
before implementing the full unified memory system.

Usage:
    from app.utils.neo4j_connection import test_neo4j_connection
    success, info = test_neo4j_connection()
"""

import logging
from typing import Tuple, Dict, Any, Optional
import os

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    logger.warning("Neo4j driver not available. Install with: pip install neo4j")
    NEO4J_AVAILABLE = False


def get_neo4j_connection_info() -> Dict[str, str]:
    """
    Get Neo4j connection information from environment variables.
    
    Returns:
        Dictionary with connection parameters
    """
    from app.settings import config
    
    return {
        "uri": config.NEO4J_URI,
        "username": config.NEO4J_USER,
        "password": config.NEO4J_PASSWORD,
        "database": os.getenv("NEO4J_DATABASE", "neo4j")  # Default Neo4j database
    }


def test_neo4j_connection(timeout: int = 5) -> Tuple[bool, Dict[str, Any]]:
    """
    Test Neo4j database connection.
    
    Args:
        timeout: Connection timeout in seconds
        
    Returns:
        Tuple of (success: bool, info: dict)
    """
    if not NEO4J_AVAILABLE:
        return False, {
            "error": "Neo4j driver not installed",
            "message": "Install with: pip install neo4j",
            "type": "dependency_missing"
        }
    
    try:
        conn_info = get_neo4j_connection_info()
        
        # Validate required parameters
        if not all([conn_info["uri"], conn_info["username"], conn_info["password"]]):
            return False, {
                "error": "Missing Neo4j credentials",
                "message": "NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD must be set",
                "type": "configuration_error"
            }
        
        # Test connection
        driver = GraphDatabase.driver(
            conn_info["uri"],
            auth=(conn_info["username"], conn_info["password"])
        )
        
        with driver.session() as session:
            # Use a simple query that works with both local Neo4j and Neo4j Aura
            result = session.run("RETURN 'Neo4j connection successful!' AS message, "
                               "'Neo4j Aura' AS version")
            record = result.single()
            
            if record:
                success_info = {
                    "message": record["message"],
                    "version": record["version"],
                    "uri": conn_info["uri"],
                    "database": conn_info["database"],
                    "type": "success"
                }
                logger.info(f"✅ Neo4j connection successful: {conn_info['uri']}")
                return True, success_info
            else:
                return False, {
                    "error": "No response from Neo4j",
                    "type": "connection_error"
                }
        
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
        
        logger.error(f"❌ Neo4j connection failed: {error_message}")
        return False, {
            "error": error_message,
            "type": error_type,
            "uri": conn_info.get("uri", "unknown")
        }
    
    finally:
        try:
            if 'driver' in locals():
                driver.close()
        except:
            pass


def is_neo4j_ready() -> bool:
    """
    Quick check if Neo4j is ready for use.
    
    Returns:
        True if Neo4j is available and configured
    """
    if not NEO4J_AVAILABLE:
        return False
    
    success, _ = test_neo4j_connection()
    return success


def get_neo4j_status() -> Dict[str, Any]:
    """
    Get comprehensive Neo4j status information.
    
    Returns:
        Dictionary with detailed status information
    """
    conn_info = get_neo4j_connection_info()
    success, result = test_neo4j_connection()
    
    status = {
        "available": NEO4J_AVAILABLE,
        "configured": bool(conn_info["uri"] and conn_info["username"] and conn_info["password"]),
        "connected": success,
        "uri": conn_info["uri"],
        "database": conn_info["database"],
        "result": result
    }
    
    # Add summary status
    if status["available"] and status["configured"] and status["connected"]:
        status["overall_status"] = "ready"
    elif not status["available"]:
        status["overall_status"] = "driver_missing"
    elif not status["configured"]:
        status["overall_status"] = "not_configured"
    else:
        status["overall_status"] = "connection_failed"
    
    return status


# Phase 1 validation function
def validate_neo4j_for_phase1() -> Tuple[bool, str]:
    """
    Validate Neo4j setup for Phase 1 migration.
    
    Returns:
        Tuple of (is_valid: bool, message: str)
    """
    status = get_neo4j_status()
    
    if status["overall_status"] == "ready":
        return True, "✅ Neo4j is ready for Phase 1 migration"
    elif status["overall_status"] == "driver_missing":
        return False, "❌ Neo4j driver not installed. Run: pip install neo4j"
    elif status["overall_status"] == "not_configured":
        return False, "❌ Neo4j not configured. Set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD"
    else:
        error_msg = status["result"].get("error", "Unknown error")
        return False, f"❌ Neo4j connection failed: {error_msg}"


if __name__ == "__main__":
    # Simple test when run directly
    print("Testing Neo4j connection...")
    success, info = test_neo4j_connection()
    
    if success:
        print(f"✅ Success: {info['message']}")
        print(f"   Version: {info['version']}")
        print(f"   URI: {info['uri']}")
    else:
        print(f"❌ Failed: {info['error']}")
        print(f"   Type: {info['type']}") 