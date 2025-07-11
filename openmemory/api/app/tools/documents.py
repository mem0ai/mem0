import logging
import json
import asyncio
import datetime
import uuid
from typing import Optional, Dict

from app.mcp_instance import mcp
from app.context import user_id_var, client_name_var, background_tasks_var
from app.database import SessionLocal
from app.utils.db import get_user_and_app
from app.config.memory_limits import MEMORY_LIMITS
from app.analytics import track_tool_usage

logger = logging.getLogger(__name__)

# Document processing queue - in-memory for now, could be Redis/Celery for production
document_processing_queue = {}
document_processing_status = {}

async def _process_document_background(
    job_id: str,
    title: str, 
    content: str, 
    document_type: str,
    source_url: Optional[str],
    metadata: Optional[dict],
    supa_uid: str,
    client_name: str
):
    """
    Background task to handle heavy document processing:
    - Store document in database
    - Create chunks for vector search
    - Generate summary memory
    - Link to memory system
    """
    try:
        from app.utils.db import get_or_create_user
        import functools

        logger.info(f"🔄 Starting background processing for document '{title}' (job: {job_id})")
        document_processing_status[job_id] = {
            "status": "processing",
            "message": "Processing document...",
            "progress": 10,
            "started_at": datetime.datetime.now(datetime.UTC).isoformat()
        }
        
        # 1. Validate input
        if not title.strip():
            raise ValueError("Document title cannot be empty")
        if not content.strip():
            raise ValueError("Document content cannot be empty")
        if len(content) < 50:
            raise ValueError("Document content too short (minimum 50 characters)")
            
        document_processing_status[job_id]["progress"] = 20
        document_processing_status[job_id]["message"] = "Validating content..."
        
        # 2. Get user and initialize services
        logger.info(f"📝 [{job_id}] Getting user and initializing services for user {supa_uid}")
        db = SessionLocal()
        try:
            user = get_or_create_user(db, supa_uid, email=None)
            if not user:
                raise ValueError("Failed to get user information")
            logger.info(f"✅ [{job_id}] User retrieved successfully: {user.id} (type: {type(user.id)})")
            
            # Import and get/create app for document storage
            logger.info(f"📱 [{job_id}] Getting or creating app for document storage...")
            from app.utils.db import get_or_create_app
            app = get_or_create_app(db, user, "document_storage")
            logger.info(f"✅ [{job_id}] App retrieved/created: {app.id} (name: {app.name})")
            
            # Import and initialize async memory client
            logger.info(f"🧠 [{job_id}] Initializing async memory client...")
            from app.utils.memory import get_async_memory_client
            mem0_client = await get_async_memory_client()
            logger.info(f"✅ [{job_id}] Async memory client initialized successfully")
            
            document_processing_status[job_id]["progress"] = 30
            document_processing_status[job_id]["message"] = "Storing document..."
            
            # 3. Store the full document in database
            document_id = str(uuid.uuid4())
            logger.info(f"🗄️ [{job_id}] Generated document ID: {document_id}")
            
            # Insert into documents table using SQLAlchemy ORM (same as Substack sync)
            logger.info(f"💾 [{job_id}] Creating document using SQLAlchemy ORM...")
            
            # Use SQLAlchemy ORM directly - same approach as Substack sync
            from app.models import Document
            doc = Document(
                id=uuid.UUID(document_id),
                user_id=user.id,
                app_id=app.id,
                title=title,
                content=content,
                document_type=document_type,
                source_url=source_url,
                metadata_=metadata or {}
            )
            
            db.add(doc)
            db.flush()  # Get the ID without committing yet
            logger.info(f"✅ [{job_id}] Document stored successfully in database using SQLAlchemy ORM")
                
            document_processing_status[job_id]["progress"] = 50
            document_processing_status[job_id]["message"] = "Creating searchable chunks..."
            
            # 4. Create chunks for better search performance (for large documents)
            if len(content) > 2000:  # Only chunk large documents
                logger.info(f"🔍 [{job_id}] Document is large ({len(content)} chars), creating chunks...")
                chunk_size = 1000
                overlap = 200
                chunks = []
                
                for i in range(0, len(content), chunk_size - overlap):
                    chunk_content = content[i:i + chunk_size]
                    if chunk_content.strip():
                        chunks.append({
                            "id": str(uuid.uuid4()),
                            "document_id": document_id,
                            "content": chunk_content,
                            "chunk_index": len(chunks)
                        })
                
                logger.info(f"📝 [{job_id}] Created {len(chunks)} chunks for document")
                
                # Insert chunks using SQLAlchemy ORM  
                if chunks:
                    logger.info(f"💾 [{job_id}] Creating {len(chunks)} chunks using SQLAlchemy ORM...")
                    try:
                        from app.models import DocumentChunk
                        for chunk in chunks:
                            chunk_obj = DocumentChunk(
                                id=uuid.UUID(chunk["id"]),
                                document_id=uuid.UUID(chunk["document_id"]),
                                content=chunk["content"],
                                chunk_index=chunk["chunk_index"]
                            )
                            db.add(chunk_obj)
                        db.flush()  # Save chunks without committing yet
                        logger.info(f"✅ [{job_id}] {len(chunks)} chunks created successfully using SQLAlchemy ORM")
                    except Exception as chunks_error:
                        logger.error(f"💥 [{job_id}] Chunks creation failed: {chunks_error}")
                        # Continue processing even if chunks fail - not critical
            else:
                logger.info(f"📝 [{job_id}] Document is small ({len(content)} chars), skipping chunking")
                    
            document_processing_status[job_id]["progress"] = 70
            document_processing_status[job_id]["message"] = "Generating summary..."
            
            # 5. Create multiple memory strategies for document - COMPREHENSIVE MEM0 FIX
            logger.info(f"📄 [{job_id}] Creating memory for document with multiple strategies...")
            
            document_processing_status[job_id]["progress"] = 80
            document_processing_status[job_id]["message"] = "Adding to memory system..."
            
            # Strategy definitions for robust mem0 integration
            memory_strategies = []
            
            # Strategy 1: Natural conversational summary (recommended by analysis)
            if len(content) > 1000:
                natural_content = f"I stored a {document_type} document titled '{title}'. It contains {len(content):,} characters covering topics related to {title.lower()}. The document begins with: {content[:200].strip()}..."
            else:
                natural_content = f"I stored a {document_type} document titled '{title}'. Content: {content[:800].strip()}"
            
            if source_url:
                natural_content += f" Source URL: {source_url}"
                
            memory_strategies.append({
                "name": "conversational",
                "content": natural_content,
                "metadata": {
                    "source_app": "openmemory_mcp",
                    "mcp_client": client_name,
                    "document_id": document_id,
                    "document_type": document_type,
                    "is_document_summary": True
                }
            })
            
            # Strategy 2: Simple factual format (like working add_memories)
            simple_content = f"Document: {title} ({document_type}, {len(content)} chars)"
            if len(content) > 500:
                simple_content += f". Preview: {content[:400]}"
            else:
                simple_content += f". Content: {content}"
                
            memory_strategies.append({
                "name": "simple",
                "content": simple_content,
                "metadata": {
                    "source_app": "openmemory_mcp",
                    "mcp_client": client_name,
                    "document_id": document_id
                }
            })
            
            # Strategy 3: Keywords-only approach
            title_keywords = ' '.join(title.split()[:5])  # First 5 words of title
            content_keywords = ' '.join(content.split()[:20])  # First 20 words of content
            keywords_content = f"{title_keywords} {content_keywords}"
            
            memory_strategies.append({
                "name": "keywords",
                "content": keywords_content,
                "metadata": {
                    "source_app": "openmemory_mcp",
                    "document_id": document_id
                }
            })
            
            # Strategy 4: Title-only minimal approach
            memory_strategies.append({
                "name": "minimal",
                "content": f"Document: {title}",
                "metadata": {
                    "document_id": document_id
                }
            })
            
            # Try each strategy until one succeeds
            memory_result = None
            successful_strategy = None
            
            # Use same approach as working _add_memories_background_claude function
            loop = asyncio.get_running_loop()
            
            for strategy in memory_strategies:
                try:
                    logger.info(f"🔄 [{job_id}] Trying mem0 strategy '{strategy['name']}' (content: {len(strategy['content'])} chars)")
                    
                    # Use the exact same pattern as working add_memories function
                    message_to_add = {
                        "role": "user",
                        "content": strategy["content"]
                    }
                    
                    # Call async memory client directly
                    memory_result = await mem0_client.add(
                        messages=[message_to_add],
                        user_id=supa_uid,
                        metadata=strategy["metadata"]
                    )
                    
                    logger.info(f"🔍 [{job_id}] Strategy '{strategy['name']}' result: {type(memory_result)}")
                    logger.info(f"🔍 [{job_id}] Result content: {memory_result}")
                    
                    # Check if we got a valid result with memories created
                    if (isinstance(memory_result, dict) and 
                        'results' in memory_result and 
                        memory_result['results'] and 
                        len(memory_result['results']) > 0):
                        
                        successful_strategy = strategy['name']
                        logger.info(f"✅ [{job_id}] SUCCESS with strategy '{successful_strategy}' - {len(memory_result['results'])} memories created")
                        break
                    else:
                        logger.warning(f"⚠️ [{job_id}] Strategy '{strategy['name']}' returned empty results: {memory_result}")
                        
                except Exception as strategy_error:
                    logger.error(f"❌ [{job_id}] Strategy '{strategy['name']}' failed: {strategy_error}")
                    continue
            
            # Handle results based on success/failure
            if memory_result and isinstance(memory_result, dict) and 'results' in memory_result and memory_result['results']:
                logger.info(f"🎉 [{job_id}] Memory creation SUCCESS using '{successful_strategy}' strategy!")
                
                # Follow the same database linking pattern as working code
                for result in memory_result['results']:
                    mem0_memory_id_str = result.get('id')
                    if mem0_memory_id_str and result.get('event') == 'ADD':
                        logger.info(f"🆔 [{job_id}] Got memory ID from mem0: {mem0_memory_id_str}")
                        try:
                            # Link document to memory using SQLAlchemy (same as Substack sync)
                            from app.models import document_memories
                            db.execute(
                                document_memories.insert().values(
                                    document_id=doc.id,
                                    memory_id=mem0_memory_id_str
                                )
                            )
                            logger.info(f"✅ [{job_id}] Document-memory link created successfully")
                            break  # Only link to first successfully created memory
                        except Exception as link_error:
                            logger.error(f"💥 [{job_id}] Document-memory link failed: {link_error}")
                            # Continue - the document and memory are still saved
            else:
                logger.error(f"💥 [{job_id}] ALL MEMORY STRATEGIES FAILED - document stored but not indexed in mem0")
                logger.error(f"💥 [{job_id}] Final result: {memory_result}")
                # Don't raise exception - document is still stored and retrievable via deep_memory_query
                
            # Commit all changes (same as Substack sync)
            db.commit()
            logger.info(f"💾 [{job_id}] All database changes committed successfully")
            
        finally:
            db.close()
        
        document_processing_status[job_id] = {
            "status": "completed",
            "message": f"✅ Document '{title}' successfully stored and indexed",
            "progress": 100,
            "document_id": document_id,
            "completed_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "started_at": document_processing_status[job_id]["started_at"]
        }
        
        processing_time = (datetime.datetime.now(datetime.UTC) - datetime.datetime.fromisoformat(document_processing_status[job_id]["started_at"].replace('Z', '+00:00'))).total_seconds()
        logger.info(f"✅ [{job_id}] Background processing completed successfully for document '{title}' in {processing_time:.2f} seconds")
        
    except Exception as e:
        logger.error(f"❌ Error in background document processing (job: {job_id}): {e}", exc_info=True)
        # Rollback database changes on error (same as Substack sync)
        if 'db' in locals():
            try:
                db.rollback()
                logger.info(f"🔄 [{job_id}] Database changes rolled back due to error")
            except Exception as rollback_error:
                logger.error(f"❌ [{job_id}] Failed to rollback database changes: {rollback_error}")
                
        document_processing_status[job_id] = {
            "status": "failed",
            "message": f"❌ Error processing document: {str(e)}",
            "progress": 0,
            "failed_at": datetime.datetime.now(datetime.UTC).isoformat(),
            "started_at": document_processing_status.get(job_id, {}).get("started_at")
        }


@mcp.tool(description="⚡ FAST document upload. Store large documents (markdown, code, essays) in background. Returns immediately with job ID for status tracking. Perfect for entire files that would slow down chat.")
async def store_document(
    title: str, 
    content: str, 
    document_type: str = "markdown",
    source_url: Optional[str] = None,
    metadata: Optional[dict] = None
) -> str:
    """
    Lightweight document storage tool that queues processing in background.
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    background_tasks = background_tasks_var.get(None)
    
    if not supa_uid:
        return "❌ Error: User ID not available"
    if not client_name:
        return "❌ Error: Client name not available"
    
    try:
        # Quick validation
        if not title.strip():
            return "❌ Error: Document title cannot be empty"
        if not content.strip():
            return "❌ Error: Document content cannot be empty"
        if len(content) < 10:
            return "❌ Error: Document content too short"
        
        # Generate job ID for tracking
        job_id = f"doc_{int(datetime.datetime.now(datetime.UTC).timestamp())}_{str(uuid.uuid4())[:8]}"
        logger.info(f"🚀 [QUEUE] Generated job ID {job_id} for document '{title}' (user: {supa_uid}, client: {client_name})")
        
        # Store in processing queue
        document_processing_queue[job_id] = {
            "title": title,
            "content": content,
            "document_type": document_type,
            "source_url": source_url,
            "metadata": metadata,
            "user_id": supa_uid,
            "client_name": client_name,
            "queued_at": datetime.datetime.now(datetime.UTC).isoformat()
        }
        
        # Initialize status
        document_processing_status[job_id] = {
            "status": "queued",
            "message": "Document queued for processing...",
            "progress": 0,
            "queued_at": datetime.datetime.now(datetime.UTC).isoformat()
        }
        logger.info(f"📋 [QUEUE] Document queued successfully - Size: {len(content)} chars, Type: {document_type}")
        
        # Queue background processing
        if background_tasks:
            logger.info(f"⚡ [QUEUE] Scheduling background task via FastAPI BackgroundTasks for job {job_id}")
            background_tasks.add_task(
                _process_document_background,
                job_id=job_id,
                title=title,
                content=content,
                document_type=document_type,
                source_url=source_url,
                metadata=metadata,
                supa_uid=supa_uid,
                client_name=client_name
            )
        else:
            # Fallback: create simple BackgroundTasks if not available
            logger.info(f"⚡ [QUEUE] Scheduling background task via asyncio.create_task for job {job_id}")
            asyncio.create_task(_process_document_background(
                job_id=job_id,
                title=title,
                content=content,
                document_type=document_type,
                source_url=source_url,
                metadata=metadata,
                supa_uid=supa_uid,
                client_name=client_name
            ))
        
        # Immediate lightweight response
        content_preview = content[:100] + "..." if len(content) > 100 else content
        
        return f"""🚀 **Document Upload Started**

📄 **Title:** {title}
📊 **Size:** {len(content):,} characters
🔄 **Job ID:** `{job_id}`
⏱️ **Status:** Queued for background processing

Your document is being processed in the background. This includes:
- ✅ Secure storage in database
- 🔍 Creating searchable chunks  
- 🧠 Adding to memory system with multiple retry strategies
- 🔗 Linking for future retrieval

Processing typically completes within 30-60 seconds. Your document will then be searchable via regular memory tools and deep_memory_query.

**Preview:** {content_preview}"""

    except Exception as e:
        logger.error(f"Error in store_document MCP tool: {e}", exc_info=True)
        return f"❌ Error queueing document: {e}"

@mcp.tool(description="Check the processing status of a document upload using the job ID returned by store_document.")
async def get_document_status(job_id: str) -> str:
    """
    Check the status of a background document processing job.
    """
    try:
        if job_id not in document_processing_status:
            return f"❌ Job ID '{job_id}' not found. Please check the job ID."
        
        status_info = document_processing_status[job_id]
        status = status_info.get("status", "unknown")
        message = status_info.get("message", "No message")
        progress = status_info.get("progress", 0)
        
        # Status icons
        status_icons = {
            "queued": "⏳",
            "processing": "🔄", 
            "completed": "✅",
            "failed": "❌"
        }
        
        icon = status_icons.get(status, "❓")
        
        response = f"""📋 **Document Processing Status**

🔍 **Job ID:** `{job_id}`
{icon} **Status:** {status.upper()}
📊 **Progress:** {progress}%
💬 **Message:** {message}
"""
        
        # Add timing information
        if "queued_at" in status_info:
            response += f"⏰ **Queued:** {status_info['queued_at']}\n"
        if "started_at" in status_info:
            response += f"🚀 **Started:** {status_info['started_at']}\n"
        if "completed_at" in status_info:
            response += f"✅ **Completed:** {status_info['completed_at']}\n"
        if "failed_at" in status_info:
            response += f"❌ **Failed:** {status_info['failed_at']}\n"
        
        # Add document ID if completed
        if status == "completed" and "document_id" in status_info:
            response += f"\n📄 **Document ID:** `{status_info['document_id']}`"
            response += f"\n🔍 **Next Steps:** Your document is now searchable via regular memory tools!"
        
        return response
        
    except Exception as e:
        logger.error(f"Error checking document status: {e}", exc_info=True)
        return f"❌ Error checking status: {e}"

@mcp.tool(description="Sync Substack posts for the user. Provide the Substack URL (e.g., https://username.substack.com or username.substack.com). Note: This process may take 30-60 seconds depending on the number of posts being processed.")
async def sync_substack_posts(substack_url: str, max_posts: int = 20) -> str:
    from app.integrations.substack_service import SubstackService
    
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    # Track Substack sync usage (only if private analytics available)
    track_tool_usage('sync_substack_posts', {
        'substack_url_length': len(substack_url),
        'max_posts': max_posts
    })
    
    # Let user know we're starting
    logger.info(f"Starting Substack sync for {substack_url}")
    
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
            
            # Enhanced return message
            if synced_count > 0:
                return f"✅ {message}\n\n📊 Processed {synced_count} posts and added them to your memory system. Posts are now searchable using memory tools."
            else:
                return f"⚠️ {message}"
            
        finally:
            db.close()
    except Exception as e:
        logging.error(f"Error in sync_substack_posts MCP tool: {e}", exc_info=True)
        return f"❌ Error syncing Substack: {str(e)}"


@mcp.tool(description="Deep memory search with automatic full document inclusion. Use this for: 1) Reading/summarizing specific essays (e.g. 'summarize The Irreverent Act'), 2) Analyzing personality/writing style across documents, 3) Finding insights from essays written months/years ago, 4) Any query needing full essay context. Automatically detects and includes complete relevant documents using dynamic scoring.")
async def deep_memory_query(search_query: str, memory_limit: int = None, chunk_limit: int = None, include_full_docs: bool = True) -> str:
    """
    Performs a deep, comprehensive search across ALL user content using Gemini.
    Automatically detects when specific documents/essays are referenced and includes their full content.
    This is thorough but slower - use search_memory for simple queries.
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    try:
        # Track deep memory usage (only if private analytics available)
        track_tool_usage('deep_memory_query', {
            'query_length': len(search_query),
            'memory_limit': memory_limit,
            'chunk_limit': chunk_limit,
            'include_full_docs': include_full_docs
        })
        
        # Add timeout to prevent hanging - 60 seconds max
        return await asyncio.wait_for(
            _deep_memory_query_impl(search_query, supa_uid, client_name, memory_limit, chunk_limit, include_full_docs),
            timeout=60.0
        )
    except asyncio.TimeoutError:
        return f"Deep memory search timed out for query '{search_query}'. Try using 'search_memory' for faster results, or simplify your query."
    except Exception as e:
        logger.error(f"Error in deep_memory_query: {e}", exc_info=True)
        return f"Error performing deep search: {str(e)}"


async def _deep_memory_query_impl(search_query: str, supa_uid: str, client_name: str, memory_limit: int = None, chunk_limit: int = None, include_full_docs: bool = True) -> str:
    """Optimized implementation of deep_memory_query"""
    from app.utils.memory import get_memory_client, get_async_memory_client
    from app.utils.gemini import GeminiService
    from app.services.chunking_service import ChunkingService
    from app.models import Document
    
    # Use configured limits - NO HARDCODED CAPS! Let it use hundreds of memories
    if memory_limit is None:
        memory_limit = MEMORY_LIMITS.deep_memory_default  # Now 200!
    if chunk_limit is None:
        chunk_limit = MEMORY_LIMITS.deep_chunk_default    # Now 50!
    memory_limit = min(max(1, memory_limit), MEMORY_LIMITS.deep_memory_max)  # Up to 500 memories!
    chunk_limit = min(max(1, chunk_limit), MEMORY_LIMITS.deep_chunk_max)     # Up to 100 chunks!
    
    import time
    start_time = time.time()
    logger.info(f"deep_memory_query: Starting for user {supa_uid}")
    
    try:
        db = SessionLocal()
        try:
            # Get user and app
            user, app = get_user_and_app(db, supa_uid, client_name)
            if not user or not app:
                return "Error: User or app not found"
            
            # Initialize services
            memory_client = await get_async_memory_client()
            gemini_service = GeminiService()
            chunking_service = ChunkingService()
            
            # 1. Get ALL memories for comprehensive context
            mem_fetch_start_time = time.time()
            all_memories_result = await memory_client.get_all(user_id=supa_uid, limit=memory_limit)
            search_memories_result = await memory_client.search(
                query=search_query,
                user_id=supa_uid,
                limit=memory_limit
            )
            mem_fetch_duration = time.time() - mem_fetch_start_time
            
            # Combine and prioritize memories
            all_memories = []
            search_memories = []
            
            if isinstance(all_memories_result, dict) and 'results' in all_memories_result:
                all_memories = all_memories_result['results']
            elif isinstance(all_memories_result, list):
                all_memories = all_memories_result
                
            if isinstance(search_memories_result, dict) and 'results' in search_memories_result:
                search_memories = search_memories_result['results']
            elif isinstance(search_memories_result, list):
                search_memories = search_memories_result
            
            # Prioritize search results, then add other memories
            memory_ids_seen = set()
            prioritized_memories = []
            
            # Add search results first
            for mem in search_memories:
                if isinstance(mem, dict) and mem.get('id'):
                    memory_ids_seen.add(mem['id'])
                    prioritized_memories.append(mem)
            
            # Add other memories up to limit
            for mem in all_memories:
                if len(prioritized_memories) >= memory_limit:
                    break
                if isinstance(mem, dict) and mem.get('id') and mem['id'] not in memory_ids_seen:
                    prioritized_memories.append(mem)
            
            logger.info(f"deep_memory_query: Memory fetching for user {supa_uid} took {mem_fetch_duration:.2f}s. Found {len(prioritized_memories)} memories.")

            # 2. Get ALL documents for comprehensive analysis
            doc_fetch_start_time = time.time()
            all_db_documents = db.query(Document).filter(
                Document.user_id == user.id
            ).order_by(Document.created_at.desc()).limit(20).all()
            doc_fetch_duration = time.time() - doc_fetch_start_time
            logger.info(f"deep_memory_query: Document fetching for user {supa_uid} took {doc_fetch_duration:.2f}s. Found {len(all_db_documents)} documents.")
            
            # Smart document selection based on query
            query_lower = search_query.lower()
            query_words = [w for w in query_lower.split() if len(w) > 2]
            selected_documents = []
            
            # Score each document for relevance
            for doc in all_db_documents:
                doc_title_lower = doc.title.lower()
                doc_content_lower = doc.content.lower() if doc.content else ""
                relevance_score = 0
                match_reasons = []
                
                # Title matching (highest priority)
                for word in query_words:
                    if word in doc_title_lower:
                        relevance_score += 10
                        match_reasons.append("title_keyword")
                
                # Check if entire title appears in query
                if doc_title_lower in query_lower:
                    relevance_score += 50
                    match_reasons.append("exact_title")
                
                # Content relevance scoring
                if doc_content_lower:
                    for word in query_words:
                        count = doc_content_lower.count(word)
                        relevance_score += min(count, 5)
                
                # Thematic matching
                if any(theme in query_lower for theme in ["personality", "values", "philosophy", "beliefs"]):
                    if any(word in doc_content_lower[:2000] for word in ["i think", "i believe", "my view"]):
                        relevance_score += 7
                        match_reasons.append("thematic_match")
                
                if relevance_score > 0:
                    selected_documents.append((doc, relevance_score, match_reasons))
            
            # Sort by relevance
            selected_documents.sort(key=lambda x: x[1], reverse=True)
            
            # If no documents matched but query seems to want documents, include recent ones
            if not selected_documents and any(word in query_lower for word in ["essay", "document", "post"]):
                selected_documents = [(doc, 1, ["recent"]) for doc in all_db_documents[:3]]
            
            # 3. Search document chunks
            chunk_search_start_time = time.time()
            relevant_chunks = []
            semantic_chunks = chunking_service.search_chunks(
                db=db,
                query=search_query,
                user_id=str(user.id),
                limit=chunk_limit
            )
            relevant_chunks.extend(semantic_chunks)
            chunk_search_duration = time.time() - chunk_search_start_time
            logger.info(f"deep_memory_query: Chunk searching for user {supa_uid} took {chunk_search_duration:.2f}s. Found {len(relevant_chunks)} chunks.")
            
            # 4. Build comprehensive context
            context = "=== USER'S COMPLETE KNOWLEDGE BASE ===\n\n"
            
            # Add memories with rich context
            if prioritized_memories:
                context += "=== MEMORIES (Thoughts, Experiences, Facts) ===\n\n"
                for i, mem in enumerate(prioritized_memories, 1):
                    if isinstance(mem, dict):
                        memory_text = mem.get('memory', mem.get('content', str(mem)))
                        metadata = mem.get('metadata', {})
                        created_at = mem.get('created_at', 'Unknown date')
                        
                        context += f"Memory {i}:\n"
                        context += f"Content: {memory_text}\n"
                        context += f"Date: {created_at}\n"
                        
                        if metadata:
                            source_app = metadata.get('source_app', 'Unknown')
                            context += f"Source: {source_app}\n"
                        context += "\n"
                context += "\n"
            
            # Add document information
            if all_db_documents:
                context += "=== ALL DOCUMENTS (Essays, Posts, Articles) ===\n\n"
                for i, doc in enumerate(all_db_documents, 1):
                    context += f"Document {i}: {doc.title}\n"
                    context += f"Type: {doc.document_type}\n"
                    context += f"URL: {doc.source_url or 'No URL'}\n"
                    context += f"Created: {doc.created_at}\n"
                    
                    if doc.content:
                        if len(doc.content) > 200:
                            context += f"Preview: {doc.content[:200]}...\n"
                        else:
                            context += f"Content: {doc.content}\n"
                    context += "\n"
                context += "\n"
            
            # Add relevant chunks
            if relevant_chunks:
                context += "=== RELEVANT DOCUMENT EXCERPTS ===\n\n"
                for i, chunk in enumerate(relevant_chunks, 1):
                    doc = next((d for d in all_db_documents if d.id == chunk.document_id), None)
                    if doc:
                        context += f"Excerpt {i} from '{doc.title}':\n"
                        context += f"Content: {chunk.content}\n\n"
                context += "\n"
            
            # 5. Include full documents based on relevance
            if include_full_docs and selected_documents:
                context += "=== FULL DOCUMENT CONTENT ===\n\n"
                
                docs_included = 0
                for doc, score, reasons in selected_documents:
                    if docs_included >= 3:  # Reasonable limit
                        break
                        
                    context += f"=== FULL CONTENT: {doc.title} ===\n"
                    context += f"Type: {doc.document_type}\n"
                    context += f"Relevance Score: {score} ({', '.join(reasons)})\n\n"
                    
                    if doc.content:
                        context += doc.content
                    
                    context += "\n\n" + "="*50 + "\n\n"
                    docs_included += 1
            
            # 6. Comprehensive prompt
            prompt = f"""You are an AI assistant with access to a comprehensive knowledge base about a specific user. Answer their question using all available information.

USER'S QUESTION: {search_query}

{context}

INSTRUCTIONS:
1. Answer comprehensively using the provided information
2. Draw connections between different pieces of information
3. Cite specific sources when making points
4. Be conversational and insightful
5. If you notice patterns across sources, point them out
6. If information is missing, be honest about limitations

Provide a thorough, insightful response."""
            
            # 7. Generate response using the new GeminiService
            gemini_start_time = time.time()
            logger.info(f"deep_memory_query: Starting Gemini Flash call for user {supa_uid}")
            
            response_text = await gemini_service.generate_response(prompt)

            gemini_duration = time.time() - gemini_start_time
            logger.info(f"deep_memory_query: Gemini Flash call for user {supa_uid} took {gemini_duration:.2f}s")
            
            processing_time = time.time() - start_time
            result = response_text
            result += f"\n\n📊 Deep Analysis: total={processing_time:.2f}s, mem_fetch={mem_fetch_duration:.2f}s, doc_fetch={doc_fetch_duration:.2f}s, chunk_search={chunk_search_duration:.2f}s, gemini={gemini_duration:.2f}s"
            
            return result
            
        finally:
            db.close()
            
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(f"Error in deep_memory_query after {processing_time:.2f}s: {e}", exc_info=True)
        return f"Error performing deep search: {str(e)}"
