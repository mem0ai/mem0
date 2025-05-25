import logging
import json
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from app.utils.memory import get_memory_client
from fastapi import FastAPI, Request
from fastapi.routing import APIRouter
import contextvars
import os
from dotenv import load_dotenv
from app.database import SessionLocal
from app.models import Memory, MemoryState, MemoryStatusHistory, MemoryAccessLog, Document
from app.utils.db import get_user_and_app, get_or_create_user
import uuid
import datetime
from app.utils.permissions import check_memory_access_permissions
from qdrant_client import models as qdrant_models
from app.integrations.substack_service import SubstackService
from app.utils.gemini import GeminiService
import asyncio

# Load environment variables
load_dotenv()

# Initialize MCP
mcp = FastMCP("mem0-mcp-server")

# DO NOT initialize memory_client globally:
# memory_client = get_memory_client()

# Context variables for user_id (Supabase User ID string) and client_name
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("supa_user_id")
client_name_var: contextvars.ContextVar[str] = contextvars.ContextVar("client_name")

# Create a router for MCP endpoints
mcp_router = APIRouter(prefix="/mcp")

# Initialize SSE transport
sse = SseServerTransport("/mcp/messages/")

@mcp.tool(description="Add new memories to the user's memory")
async def add_memories(text: str) -> str:
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    memory_client = get_memory_client() # Initialize client when tool is called

    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"

    try:
        db = SessionLocal()
        try:
            user, app = get_user_and_app(db, supabase_user_id=supa_uid, app_name=client_name, email=None)

            if not app.is_active:
                return f"Error: App {app.name} is currently paused. Cannot create new memories."

            response = memory_client.add(
                messages=text,
                user_id=supa_uid,
                metadata={
                    "source_app": "openmemory_mcp",
                    "mcp_client": client_name,
                    "app_db_id": str(app.id)
                }
            )

            if isinstance(response, dict) and 'results' in response:
                for result in response['results']:
                    mem0_memory_id_str = result['id']
                    mem0_content = result.get('memory', text)

                    if result.get('event') == 'ADD':
                        sql_memory_record = Memory(
                            user_id=user.id,
                            app_id=app.id,
                            content=mem0_content,
                            state=MemoryState.active,
                            metadata_={**result.get('metadata', {}), "mem0_id": mem0_memory_id_str}
                        )
                        db.add(sql_memory_record)
                        db.flush()  # Flush to get the memory ID before creating history
                        
                        # Don't create history for initial creation since old_state cannot be NULL
                        # The memory is created with state=active, which is sufficient
                        # History tracking starts from the first state change
                    elif result.get('event') == 'DELETE':
                        # Find the existing SQL memory record by mem0_id
                        sql_memory_record = db.query(Memory).filter(
                            Memory.metadata_['mem0_id'].astext == mem0_memory_id_str,
                            Memory.user_id == user.id
                        ).first()
                        
                        if sql_memory_record:
                            sql_memory_record.state = MemoryState.deleted
                            sql_memory_record.deleted_at = datetime.datetime.now(datetime.UTC)
                            history = MemoryStatusHistory(
                                memory_id=sql_memory_record.id,
                                changed_by=user.id,
                                old_state=MemoryState.active,
                                new_state=MemoryState.deleted
                            )
                            db.add(history)
                db.commit()
            return response
        finally:
            db.close()
    except Exception as e:
        logging.error(f"Error in add_memories MCP tool: {e}", exc_info=True)
        return f"Error adding to memory: {e}"


@mcp.tool(description="Search the user's memory for memories that match the query")
async def search_memory(query: str) -> str:
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    memory_client = get_memory_client() # Initialize client when tool is called
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    try:
        db = SessionLocal()
        try:
            user, app = get_user_and_app(db, supabase_user_id=supa_uid, app_name=client_name, email=None)

            mem0_search_results = memory_client.search(query=query, user_id=supa_uid)

            processed_results = []
            actual_results_list = []
            if isinstance(mem0_search_results, dict) and 'results' in mem0_search_results:
                 actual_results_list = mem0_search_results['results']
            elif isinstance(mem0_search_results, list):
                 actual_results_list = mem0_search_results

            for mem_data in actual_results_list:
                mem0_id = mem_data.get('id')
                if not mem0_id: continue

                # Note: We're not creating MemoryAccessLog here because we don't have
                # a SQL memory_id, only a mem0 ID. The schema requires memory_id to be NOT NULL.
                # Access logging for mem0-only operations could be tracked differently if needed.
                processed_results.append(mem_data)
            
            db.commit()
            return json.dumps(processed_results, indent=2)
        finally:
            db.close()
    except Exception as e:
        logging.error(f"Error in search_memory MCP tool: {e}", exc_info=True)
        return f"Error searching memory: {e}"


@mcp.tool(description="List all memories in the user's memory")
async def list_memories() -> str:
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    memory_client = get_memory_client() # Initialize client when tool is called
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    try:
        db = SessionLocal()
        try:
            user, app = get_user_and_app(db, supabase_user_id=supa_uid, app_name=client_name, email=None)

            all_mem0_memories = memory_client.get_all(user_id=supa_uid)

            processed_results = []
            actual_results_list = []
            if isinstance(all_mem0_memories, dict) and 'results' in all_mem0_memories:
                 actual_results_list = all_mem0_memories['results']
            elif isinstance(all_mem0_memories, list):
                 actual_results_list = all_mem0_memories

            for mem_data in actual_results_list:
                mem0_id = mem_data.get('id')
                if not mem0_id: continue
                # Note: We're not creating MemoryAccessLog here because we don't have
                # a SQL memory_id, only a mem0 ID. The schema requires memory_id to be NOT NULL.
                # Access logging for mem0-only operations could be tracked differently if needed.
                processed_results.append(mem_data)
            
            db.commit()
            return json.dumps(processed_results, indent=2)
        finally:
            db.close()
    except Exception as e:
        logging.error(f"Error in list_memories MCP tool: {e}", exc_info=True)
        return f"Error getting memories: {e}"


@mcp.tool(description="Delete all memories in the user's memory")
async def delete_all_memories() -> str:
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    memory_client = get_memory_client() # Initialize client when tool is called
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    try:
        db = SessionLocal()
        try:
            user, app = get_user_and_app(db, supabase_user_id=supa_uid, app_name=client_name, email=None)

            memory_client.delete_all(user_id=supa_uid)

            sql_memories_to_delete = db.query(Memory).filter(Memory.user_id == user.id).all()
            now = datetime.datetime.now(datetime.UTC)
            for mem_record in sql_memories_to_delete:
                if mem_record.state != MemoryState.deleted:
                    history = MemoryStatusHistory(
                        memory_id=mem_record.id,
                        changed_by=user.id,
                        old_state=mem_record.state,
                        new_state=MemoryState.deleted
                    )
                    db.add(history)
                    mem_record.state = MemoryState.deleted
                    mem_record.deleted_at = now
                    
                    access_log = MemoryAccessLog(
                        memory_id=mem_record.id,
                        app_id=app.id,
                        access_type="delete_all_mcp",
                        metadata_={
                            "operation": "bulk_delete_mcp_tool",
                            "mem0_user_id_cleared": supa_uid
                        }
                    )
                    db.add(access_log)
            
            db.commit()
            return f"Successfully initiated deletion of all memories for user {supa_uid} via mem0 and updated SQL records."
        finally:
            db.close()
    except Exception as e:
        logging.error(f"Error in delete_all_memories MCP tool: {e}", exc_info=True)
        return f"Error deleting memories: {e}"


@mcp.tool(description="Sync Substack posts for the user. Provide the Substack URL (e.g., https://username.substack.com)")
async def sync_substack_posts(substack_url: str, max_posts: int = 20) -> str:
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    try:
        db = SessionLocal()
        try:
            # Use the SubstackService to handle the sync
            service = SubstackService()
            synced_count, message = await service.sync_substack_posts(
                db=db,
                supabase_user_id=supa_uid,
                substack_url=substack_url,
                max_posts=max_posts,
                use_mem0=True  # Try to use mem0, but it will gracefully degrade if not available
            )
            
            return message
            
        finally:
            db.close()
    except Exception as e:
        logging.error(f"Error in sync_substack_posts MCP tool: {e}", exc_info=True)
        return f"Error syncing Substack: {str(e)}"


@mcp.tool(description="Deep query across all user's memories and documents using Gemini's long-context capabilities. This searches through everything - regular memories, documents, essays, etc.")
async def deep_memory_query(search_query: str) -> str:
    """
    Performs a deep, comprehensive search across all user content using Gemini.
    This is the 'heavy lifting' tool that can understand context across all memories and documents.
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    try:
        db = SessionLocal()
        try:
            # Get user
            user, app = get_user_and_app(db, supabase_user_id=supa_uid, app_name=client_name, email=None)
            
            # Get ALL memories for the user (limit to most recent to avoid timeout)
            all_memories = db.query(Memory).filter(
                Memory.user_id == user.id,
                Memory.state == MemoryState.active
            ).order_by(Memory.created_at.desc()).limit(30).all()  # Reduced from 50
            
            # Convert to the format expected by Gemini
            relevant_memories = []
            for mem in all_memories:
                relevant_memories.append({
                    'memory': mem.content,
                    'content': mem.content,  # Add both for compatibility
                    'metadata': mem.metadata_ or {},
                    'created_at': mem.created_at.isoformat() if mem.created_at else None
                })
            
            # Get ALL documents for the user
            all_documents = db.query(Document).filter(
                Document.user_id == user.id
            ).order_by(Document.created_at.desc()).all()
            
            # Debug logging
            logging.info(f"Deep query: Found {len(relevant_memories)} memories and {len(all_documents)} documents")
            
            # Calculate total content size to determine strategy
            total_content_size = sum(len(doc.content) for doc in all_documents)
            total_memory_size = sum(len(mem['content']) for mem in relevant_memories)
            
            logging.info(f"Deep query: Total content size: {total_content_size + total_memory_size} chars")
            
            # Use different strategies based on content size
            if total_content_size + total_memory_size > 500000:  # 500K chars
                # Large content - use chunked approach with timeout protection
                return await _chunked_deep_query(relevant_memories, all_documents, search_query)
            else:
                # Smaller content - use full query with timeout protection
                try:
                    # Set a timeout for the Gemini call
                    gemini_service = GeminiService()
                    result = await asyncio.wait_for(
                        gemini_service.deep_query(
                            memories=relevant_memories,
                            documents=all_documents,
                            query=search_query
                        ),
                        timeout=45.0  # 45 second timeout
                    )
                    return result
                except asyncio.TimeoutError:
                    logging.warning("Deep query timed out, falling back to chunked approach")
                    return await _chunked_deep_query(relevant_memories, all_documents, search_query)
            
        finally:
            db.close()
    except Exception as e:
        logging.error(f"Error in deep_memory_query MCP tool: {e}", exc_info=True)
        return f"Error performing deep query: {str(e)}"


async def _chunked_deep_query(memories: list, documents: list, query: str) -> str:
    """
    Fallback chunked approach for large content or when main query times out
    """
    try:
        gemini_service = GeminiService()
        
        # First, search through memories only (faster)
        memory_result = ""
        if memories:
            try:
                memory_result = await asyncio.wait_for(
                    gemini_service.deep_query(
                        memories=memories,
                        documents=[],  # No documents in this pass
                        query=query
                    ),
                    timeout=20.0
                )
            except asyncio.TimeoutError:
                memory_result = "Memory search timed out."
        
        # Then search through documents in chunks
        document_results = []
        chunk_size = 2  # Process 2 documents at a time
        
        for i in range(0, len(documents), chunk_size):
            chunk = documents[i:i + chunk_size]
            try:
                chunk_result = await asyncio.wait_for(
                    gemini_service.deep_query(
                        memories=[],  # No memories in document chunks
                        documents=chunk,
                        query=query
                    ),
                    timeout=25.0
                )
                document_results.append(f"Documents {i+1}-{min(i+chunk_size, len(documents))}: {chunk_result}")
            except asyncio.TimeoutError:
                document_results.append(f"Documents {i+1}-{min(i+chunk_size, len(documents))}: Search timed out.")
            except Exception as e:
                document_results.append(f"Documents {i+1}-{min(i+chunk_size, len(documents))}: Error - {str(e)}")
        
        # Combine results
        final_result = f"=== DEEP MEMORY SEARCH RESULTS ===\n\n"
        final_result += f"Query: {query}\n\n"
        
        if memory_result:
            final_result += f"=== MEMORY ANALYSIS ===\n{memory_result}\n\n"
        
        if document_results:
            final_result += f"=== DOCUMENT ANALYSIS ===\n"
            for result in document_results:
                final_result += f"{result}\n\n"
        
        if not memory_result and not document_results:
            final_result += "No relevant information found in your memories or documents."
        
        return final_result
        
    except Exception as e:
        logging.error(f"Error in chunked deep query: {e}")
        return f"Error in fallback search: {str(e)}"


@mcp_router.get("/{client_name}/sse/{user_id}")
async def handle_sse(request: Request):
    supa_user_id_from_path = request.path_params.get("user_id")
    user_token = user_id_var.set(supa_user_id_from_path or "")
    client_name = request.path_params.get("client_name")
    client_token = client_name_var.set(client_name or "")

    try:
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as (read_stream, write_stream):
            await mcp._mcp_server.run(
                read_stream,
                write_stream,
                mcp._mcp_server.create_initialization_options(),
            )
    finally:
        user_id_var.reset(user_token)
        client_name_var.reset(client_token)


@mcp_router.post("/messages/")
async def handle_post_message(request: Request):
    """Handle POST messages for SSE"""
    try:
        body = await request.body()

        # Create a simple receive function that returns the body
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        # Create a simple send function that does nothing
        async def send(message):
            pass

        # Call handle_post_message with the correct arguments
        await sse.handle_post_message(request.scope, receive, send)

        # Return a success response
        return {"status": "ok"}
    finally:
        pass
        # Clean up context variable
        # client_name_var.reset(client_token)

def setup_mcp_server(app: FastAPI):
    """Setup MCP server with the FastAPI application"""
    mcp._mcp_server.name = f"mem0-mcp-server"

    # Include MCP router in the FastAPI app
    app.include_router(mcp_router)
