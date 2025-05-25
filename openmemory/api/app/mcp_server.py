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
import google.generativeai as genai

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
            
            # Get memories and documents
            all_memories = db.query(Memory).filter(
                Memory.user_id == user.id,
                Memory.state == MemoryState.active
            ).order_by(Memory.created_at.desc()).limit(20).all()  # Reduced further
            
            all_documents = db.query(Document).filter(
                Document.user_id == user.id
            ).order_by(Document.created_at.desc()).all()
            
            # Convert memories to expected format
            relevant_memories = []
            for mem in all_memories:
                relevant_memories.append({
                    'memory': mem.content,
                    'content': mem.content,
                    'metadata': mem.metadata_ or {},
                    'created_at': mem.created_at.isoformat() if mem.created_at else None
                })
            
            logging.info(f"Deep query: Found {len(relevant_memories)} memories and {len(all_documents)} documents")
            
            # ALWAYS use parallel chunked approach to avoid timeouts
            return await _parallel_chunked_query(relevant_memories, all_documents, search_query)
            
        finally:
            db.close()
    except Exception as e:
        logging.error(f"Error in deep_memory_query MCP tool: {e}", exc_info=True)
        return f"Error performing deep query: {str(e)}"


async def _parallel_chunked_query(memories: list, documents: list, query: str) -> str:
    """
    Parallel processing approach with orchestrating agent for super fast results
    """
    try:
        gemini_service = GeminiService()
        
        # Create tasks for parallel processing
        tasks = []
        task_descriptions = []
        
        # Task 1: Memory analysis (if we have memories)
        if memories:
            tasks.append(
                asyncio.create_task(
                    _quick_memory_search(gemini_service, memories, query)
                )
            )
            task_descriptions.append("Memory Analysis")
        
        # Task 2-N: Document chunks (process 1 document at a time for speed)
        for i, doc in enumerate(documents):
            if i >= 3:  # Limit to first 3 documents to avoid timeout
                break
            tasks.append(
                asyncio.create_task(
                    _quick_document_search(gemini_service, [doc], query, i+1)
                )
            )
            task_descriptions.append(f"Document {i+1}: {doc.title[:30]}...")
        
        # Run all tasks in parallel with aggressive timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=90.0  # Very aggressive 25-second total timeout
            )
        except asyncio.TimeoutError:
            # If we timeout, cancel remaining tasks and use what we have
            for task in tasks:
                if not task.done():
                    task.cancel()
            results = [task.result() if task.done() else "Timed out" for task in tasks]
        
        # Orchestrate results with a quick summary
        return await _orchestrate_results(gemini_service, results, task_descriptions, query)
        
    except Exception as e:
        logging.error(f"Error in parallel chunked query: {e}")
        return f"Error in parallel search: {str(e)}"


async def _quick_memory_search(gemini_service, memories: list, query: str) -> str:
    """Quick memory search with tight timeout"""
    try:
        # Build minimal context
        context = "=== MEMORIES ===\n"
        for i, mem in enumerate(memories[:10], 1):  # Limit to 10 memories
            memory_text = mem.get('memory', mem.get('content', ''))
            context += f"{i}. {memory_text[:300]}...\n"  # Truncate each memory
        
        prompt = f"""Analyze these memories for: {query}

{context}

Provide a brief analysis focusing on the query. Be concise."""
        
        response = await asyncio.wait_for(
            asyncio.to_thread(
                gemini_service.model.generate_content,
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=1024,
                )
            ),
            timeout=30.0  # Increased from 10 to 30 seconds
        )
        return response.text
    except Exception as e:
        return f"Memory search error: {str(e)}"


async def _quick_document_search(gemini_service, documents: list, query: str, doc_num: int) -> str:
    """Quick document search with tight timeout"""
    try:
        doc = documents[0]  # Should only be one document
        
        # Smart truncation for speed - but less aggressive given we have more time
        content = doc.content
        if len(content) > 40000:  # Increased from 20K to 40K chars
            content = content[:30000] + "\n[...truncated...]\n" + content[-8000:]  # More content preserved
        
        prompt = f"""Analyze this document for: {query}

Document: {doc.title}
Content: {content}

Provide a brief analysis focusing on the query. Be concise."""
        
        response = await asyncio.wait_for(
            asyncio.to_thread(
                gemini_service.model.generate_content,
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=1024,
                )
            ),
            timeout=45.0  # Increased from 12 to 45 seconds per document
        )
        return response.text
    except Exception as e:
        return f"Document {doc_num} error: {str(e)}"


async def _orchestrate_results(gemini_service, results: list, descriptions: list, query: str) -> str:
    """Orchestrating agent that combines all results"""
    try:
        # Build summary of all results
        combined_results = f"=== DEEP MEMORY SEARCH RESULTS ===\n\nQuery: {query}\n\n"
        
        for i, (result, desc) in enumerate(zip(results, descriptions)):
            if isinstance(result, Exception):
                combined_results += f"**{desc}**: Error - {str(result)}\n\n"
            elif result and "error" not in result.lower():
                combined_results += f"**{desc}**:\n{result}\n\n"
            else:
                combined_results += f"**{desc}**: {result}\n\n"
        
        # Quick orchestration with more reasonable timeout
        orchestration_prompt = f"""Synthesize these search results into a coherent answer:

{combined_results}

Original Query: {query}

Provide a unified, comprehensive response that draws connections across all sources. Be specific and cite sources."""
        
        try:
            final_response = await asyncio.wait_for(
                asyncio.to_thread(
                    gemini_service.model.generate_content,
                    orchestration_prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=0.7,
                        max_output_tokens=2048,
                    )
                ),
                timeout=20.0  # Increased from 8 to 20 seconds for orchestration
            )
            return final_response.text
        except asyncio.TimeoutError:
            # If orchestration times out, return the raw results
            return combined_results + "\n[Note: Final synthesis timed out, showing raw results]"
        
    except Exception as e:
        # Fallback to just returning what we have
        return f"=== SEARCH RESULTS (Raw) ===\n\nQuery: {query}\n\n" + "\n".join([str(r) for r in results if r])


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
