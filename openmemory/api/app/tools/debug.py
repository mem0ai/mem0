import logging
import datetime
import os
import json

from app.mcp_instance import mcp
from app.context import user_id_var, client_name_var
from app.database import SessionLocal
from app.utils.db import get_user_and_app
from app.models import Document
from app.analytics import track_tool_usage

logger = logging.getLogger(__name__)

def _track_tool_usage(tool_name: str, properties: dict = None):
    """Analytics tracking - only active if enabled via environment variable"""
    pass

@mcp.tool(description="DEBUG: Directly fetch a point's payload from Qdrant.")
async def debug_get_qdrant_payload(point_id: str) -> str:
    """
    A temporary debugging tool to directly inspect a point's payload in Qdrant,
    bypassing the mem0 library's search function to verify if metadata is being written.
    """
    from qdrant_client import QdrantClient

    try:
        qdrant_host = os.getenv("QDRANT_HOST")
        qdrant_api_key = os.getenv("QDRANT_API_KEY")
        collection_name = os.getenv("MAIN_QDRANT_COLLECTION_NAME")

        if not all([qdrant_host, collection_name]):
            return "Error: Missing Qdrant environment variables for debugging."

        client = QdrantClient(
            url=f"https://{qdrant_host}",
            api_key=qdrant_api_key,
        )

        logger.info(f"🔍 DEBUG_QDRANT: Attempting to retrieve point '{point_id}' from collection '{collection_name}'")

        points = client.retrieve(
            collection_name=collection_name,
            ids=[point_id],
            with_payload=True,
            with_vectors=False
        )

        if not points:
            return f"Error: Point with ID '{point_id}' not found in Qdrant collection '{collection_name}'."

        point_data = points[0]
        payload = point_data.payload

        logger.info(f"🔍 DEBUG_QDRANT: Successfully retrieved payload for point '{point_id}': {payload}")

        return json.dumps(payload, indent=2)

    except Exception as e:
        logger.error(f"Error in debug_get_qdrant_payload: {e}", exc_info=True)
        return f"An unexpected error occurred while debugging Qdrant: {str(e)}"


@mcp.tool(description="Test MCP connection and verify all systems are working")
async def test_connection() -> str:
    """
    Test the MCP connection and verify that all systems are working properly.
    This is useful for diagnosing connection issues.
    """
    from app.utils.memory import get_memory_client
    from app.utils.gemini import GeminiService
    
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "❌ Error: Supabase user_id not available in context. Connection may be broken."
    if not client_name:
        return "❌ Error: client_name not available in context. Connection may be broken."
    
    try:
        # Track test connection usage (only if private analytics available)
        track_tool_usage('test_connection', {})
        
        db = SessionLocal()
        try:
            # Test database connection
            user, app = get_user_and_app(db, supa_uid, client_name)
            if not user or not app:
                return f"❌ Database connection failed: User or app not found for {supa_uid}/{client_name}"
            
            # Test memory client
            memory_client = get_memory_client()
            test_memories = memory_client.get_all(user_id=supa_uid, limit=1)
            
            # Test Gemini service
            gemini_service = GeminiService()
            
            # Build status report
            status_report = "🔍 MCP Connection Test Results:\n\n"
            status_report += f"✅ User ID: {supa_uid}\n"
            status_report += f"✅ Client: {client_name}\n"
            status_report += f"✅ Database: Connected (User: {user.email or 'No email'}, App: {app.name})\n"
            status_report += f"✅ Memory Client: Connected\n"
            status_report += f"✅ Gemini Service: Available\n"
            
            # Memory count
            if isinstance(test_memories, dict) and 'results' in test_memories:
                memory_count = len(test_memories['results'])
            elif isinstance(test_memories, list):
                memory_count = len(test_memories)
            else:
                memory_count = 0
            
            status_report += f"📊 Available memories: {memory_count}\n"
            
            # Document count
            doc_count = db.query(Document).filter(Document.user_id == user.id).count()
            status_report += f"📄 Available documents: {doc_count}\n"
            
            status_report += f"\n🎉 All systems operational! Connection is healthy."
            status_report += f"\n⏰ Test completed at: {datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            
            return status_report
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in test_connection: {e}", exc_info=True)
        return f"❌ Connection test failed: {str(e)}\n\n💡 Try restarting Claude Desktop if this persists." 