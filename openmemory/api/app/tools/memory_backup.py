import logging
from typing import Optional, List

# Import from modularized components
from .memory_modules.utils import safe_json_dumps, track_tool_usage
from .memory_modules.search_operations import (
    search_memory, search_memory_v2, ask_memory, smart_memory_query
)
from .memory_modules.crud_operations import (
    add_memories, add_observation, list_memories, 
    delete_all_memories, get_memory_details
)

logger = logging.getLogger(__name__)


class DateTimeJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        elif isinstance(obj, datetime.date):
            return obj.isoformat()
        return super().default(obj)


def safe_json_dumps(data, **kwargs):
    """Safely serialize data to JSON, handling datetime objects"""
    try:
        return json.dumps(data, cls=DateTimeJSONEncoder, **kwargs)
    except Exception as e:
        # Fallback: convert data to string representation
        logger.warning(f"JSON serialization failed, using fallback: {e}")
        try:
            return json.dumps(str(data), **kwargs)
        except Exception as fallback_error:
            logger.error(f"Fallback JSON serialization also failed: {fallback_error}")
            return f'{{"error": "Serialization failed", "data_preview": "{str(data)[:200]}"}}'


def _track_tool_usage(tool_name: str, properties: dict = None):
    """Analytics tracking - only active if enabled via environment variable"""
    # Placeholder for the actual analytics call to avoid breaking the code.
    # The original implementation in mcp_server can be moved to a dedicated analytics module.
    pass


@mcp.tool(description="Add new memories to the user's memory")
@retry_on_exception(retries=3, delay=1, backoff=2, exceptions=(ConnectionError,))
async def add_memories(text: str, tags: Optional[list[str]] = None, priority: bool = False) -> str:
    """
    Add memories to the user's personal memory bank.
    These memories are stored in a vector database and can be searched later.
    Optionally, add a list of string tags for later filtering.
    Set priority=True for core directives that should always be remembered.
    """
    # Lazy import
    from app.utils.memory import get_async_memory_client
    import time
    start_time = time.time()
    
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    logger.info(f"add_memories: Starting for user {supa_uid}")

    # 🚨 CRITICAL: Add comprehensive logging to detect contamination
    logger.error(f"🔍 ADD_MEMORIES DEBUG - User ID from context: {supa_uid}")
    logger.error(f"🔍 ADD_MEMORIES DEBUG - Client name from context: {client_name}")
    logger.error(f"🔍 ADD_MEMORIES DEBUG - Memory content preview: {text[:100]}...")

    
    memory_client = await get_async_memory_client()

    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"

    # Detect if this is Claude Desktop for simpler response
    is_claude_desktop = (client_name not in ["chatgpt", "default_agent_app"] and 
                        not client_name.startswith("api_"))

    # For Claude Desktop: return immediately and process in background
    if is_claude_desktop:
        # Start background task - fire and forget
        asyncio.create_task(_add_memories_background_claude(text, tags, supa_uid, client_name, priority))
        
        # Return immediately for instant response
        return "✅ Memory added."

    # For API users and other clients: keep synchronous for reliability
    try:
        # Track memory addition (only if private analytics available)
        track_tool_usage('add_memories', {
            'text_length': len(text),
            'has_tags': bool(tags),
            'is_priority': priority
        })
        
        db_start_time = time.time()
        db = SessionLocal()
        db_duration = time.time() - db_start_time
        logger.info(f"add_memories: DB connection for user {supa_uid} took {db_duration:.2f}s")
        try:
            user, app = get_user_and_app(db, supabase_user_id=supa_uid, app_name=client_name, email=None)
            
            # Check if user is trying to use Pro feature (tags)
            if tags and tags:  # If tags are provided and not empty
                try:
                    SubscriptionChecker.check_pro_features(user, "metadata tagging")
                except Exception as e:
                    return f"Error: {str(e)}"

            if not app.is_active:
                return f"Error: App {app.name} is currently paused. Cannot create new memories."

            mem0_start_time = time.time()
            logger.info(f"add_memories: Starting mem0 client call for user {supa_uid}")

            metadata = {
                "source_app": "openmemory_mcp",
                "mcp_client": client_name,
                "app_db_id": str(app.id)
            }
            
            # Ensure tags is a list if it's None
            if tags is None:
                tags = []
            
            # Add the priority tag if specified
            if priority and 'priority' not in tags:
                tags.append('priority')

            if tags:
                metadata['tags'] = tags

            message_to_add = {
                "role": "user",
                "content": text
            }

            logger.info(f"🔍 DEBUG: Passing this metadata to mem0.add: {metadata}")

            # Call async memory client directly
            response = await memory_client.add(
                messages=[message_to_add],
                user_id=supa_uid,
                metadata=metadata
            )

            mem0_duration = time.time() - mem0_start_time
            logger.info(f"add_memories: mem0 client call for user {supa_uid} took {mem0_duration:.2f}s")

            if isinstance(response, dict) and 'results' in response:
                added_count = 0
                updated_count = 0
                first_added_id = None
                
                for result in response['results']:
                    mem0_memory_id_str = result['id']
                    mem0_content = result.get('memory', text)

                    # Handle both sync (with 'event' field) and async (without 'event' field) responses
                    event_type = result.get('event', 'ADD')  # Default to ADD for async responses

                    # Capture the ID of the first memory that is ADDED
                    if event_type == 'ADD' and not first_added_id:
                        first_added_id = mem0_memory_id_str

                    if event_type == 'ADD':
                        # Create simplified metadata schema
                        sql_metadata = {
                            "mem0_id": mem0_memory_id_str
                        }
                        
                        sql_memory_record = Memory(
                            user_id=user.id,
                            app_id=app.id,
                            content=mem0_content,
                            state=MemoryState.active,
                            metadata_=sql_metadata
                            # created_at and updated_at will be set automatically by the model
                        )
                        db.add(sql_memory_record)
                        db.flush()  # Flush to get the memory ID before creating history
                        added_count += 1
                        
                        # Don't create history for initial creation since old_state cannot be NULL
                        # The memory is created with state=active, which is sufficient
                        # History tracking starts from the first state change
                    elif event_type == 'DELETE':
                        # Find the existing SQL memory record by mem0_id
                        sql_memory_record = db.query(Memory).filter(
                            text("metadata_->>'mem0_id' = :mem0_id"),
                            Memory.user_id == user.id
                        ).params(mem0_id=mem0_memory_id_str).first()
                        
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
                    elif event_type == 'UPDATE':
                        # Handle UPDATE events (though rare in async responses)
                        pass
                        
                db_commit_start_time = time.time()
                db.commit()
                db_commit_duration = time.time() - db_commit_start_time
                logger.info(f"add_memories: DB commit for user {supa_uid} took {db_commit_duration:.2f}s")
                
                # Detailed response for API users and other clients
                response_message = ""
                if added_count > 0:
                    response_message = f"Successfully added {added_count} new memory(ies)."
                elif updated_count > 0:
                    response_message = f"Updated {updated_count} existing memory(ies)."
                else:
                    response_message = "Memory processed but no changes made (possibly duplicate)."

                response_data = {
                    "message": response_message,
                    "first_added_id": first_added_id,
                    "content_preview": f"{text[:100]}{'...' if len(text) > 100 else ''}"
                }
                return json.dumps(response_data)
            else:
                # Handle case where response doesn't have expected format
                total_duration = time.time() - start_time
                return json.dumps({"message": f"Memory processed successfully in {total_duration:.2f}s.", "response_preview": f"{str(response)[:200]}{'...' if len(str(response)) > 200 else ''}"})
        finally:
            db.close()
    except Exception as e:
        total_duration = time.time() - start_time
        logging.error(f"Error in add_memories MCP tool after {total_duration:.2f}s: {e}", exc_info=True)
        return f"Error adding to memory: {e}"


async def _add_memories_background_claude(text: str, tags: Optional[list[str]], supa_uid: str, client_name: str, priority: bool = False):
    """Background memory processing for Claude Desktop - fire and forget"""
    try:
        # Use async memory client for proper response format
        from app.utils.memory import get_async_memory_client
        
        memory_client = await get_async_memory_client()
        
        # Track memory addition (only if private analytics available)
        track_tool_usage('add_memories', {
            'text_length': len(text),
            'has_tags': bool(tags),
            'is_priority': priority
        })
        
        db = SessionLocal()
        try:
            user, app = get_user_and_app(db, supabase_user_id=supa_uid, app_name=client_name, email=None)
            
            # Skip Pro features check for background - just ignore tags if not Pro
            if tags and tags:
                try:
                    SubscriptionChecker.check_pro_features(user, "metadata tagging")
                except Exception:
                    tags = None  # Just remove tags instead of failing
                    
            if not app.is_active:
                logger.warning(f"Background memory add skipped - app {app.name} is paused for user {supa_uid}")
                return

            metadata = {
                "source_app": "openmemory_mcp",
                "mcp_client": client_name,
                "app_db_id": str(app.id)
            }

            # Ensure tags is a list if it's None
            if tags is None:
                tags = []
            
            # Add the priority tag if specified
            if priority and 'priority' not in tags:
                tags.append('priority')

            if tags:
                metadata['tags'] = tags

            message_to_add = {
                "role": "user",
                "content": text
            }

            # Call async memory client directly
            response = await memory_client.add(
                messages=[message_to_add],
                user_id=supa_uid,
                metadata=metadata
            )

            logger.info(f"🔍 Background: mem0 response type: {type(response)}")
            logger.info(f"🔍 Background: mem0 response preview: {str(response)[:200]}...")

            if isinstance(response, dict) and 'results' in response:
                added_count = 0
                for result in response['results']:
                    mem0_memory_id_str = result['id']
                    mem0_content = result.get('memory', text)

                    # Handle both sync (with 'event' field) and async (without 'event' field) responses
                    event_type = result.get('event', 'ADD')  # Default to ADD for async responses
                    
                    if event_type == 'ADD':
                        # Create simplified metadata schema
                        sql_metadata = {
                            "mem0_id": mem0_memory_id_str
                        }
                        
                        sql_memory_record = Memory(
                            user_id=user.id,
                            app_id=app.id,
                            content=mem0_content,
                            state=MemoryState.active,
                            metadata_=sql_metadata
                            # created_at and updated_at will be set automatically by the model
                        )
                        db.add(sql_memory_record)
                        added_count += 1
                        logger.info(f"🔍 Background: Added SQL record for mem0_id {mem0_memory_id_str}: '{mem0_content[:50]}...')")
                    elif event_type == 'DELETE':
                        sql_memory_record = db.query(Memory).filter(
                            text("metadata_->>'mem0_id' = :mem0_id"),
                            Memory.user_id == user.id
                        ).params(mem0_id=mem0_memory_id_str).first()
                        
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
                logger.info(f"🔍 Background: Committed {added_count} SQL records to database")
                logger.info(f"Background memory add completed for user {supa_uid}: {text[:50]}...")
            else:
                # Fallback: If response format is unexpected, log warning but don't fail
                logger.warning(f"🔍 Background: Unexpected response format - no 'results' key found")
                logger.warning(f"🔍 Background: Response: {response}")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Background memory add failed for user {supa_uid}: {e}", exc_info=True)
        # Don't re-raise - this is fire and forget


@mcp.tool(description="Add new memory/fact/observation about the user. Use this to save: 1) Important information learned in conversation, 2) User preferences/values/beliefs, 3) Facts about their work/life/interests, 4) Anything the user wants remembered. The memory will be permanently stored and searchable.")
async def add_observation(text: str) -> str:
    """
    This is an alias for the add_memories tool with a more descriptive prompt for the agent.
    Functionally, it performs the same action.
    """
    # This function now simply calls the other one to avoid code duplication.
    # Note: This alias does not expose the 'tags' parameter.
    return await add_memories(text)


@mcp.tool(description="Search the user's memory for memories that match the query. Optionally filter by tags.")
@retry_on_exception(retries=3, delay=1, backoff=2, exceptions=(ConnectionError,))
async def search_memory(query: str, limit: int = None, tags_filter: Optional[list[str]] = None) -> str:
    """
    Search the user's memory for memories that match the query.
    Returns memories that are semantically similar to the query.
    
    Args:
        query: The search term or phrase to look for
        limit: Maximum number of results to return (default: 10, max: 50) 
        tags_filter: Optional list of tags to filter results (e.g., ["work", "project-alpha"])
                    Only memories containing ALL specified tags will be returned.
    
    Returns:
        JSON string containing list of matching memories with their content and metadata
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    # Use configured limits
    if limit is None:
        limit = MEMORY_LIMITS.search_default
    limit = min(max(1, limit), MEMORY_LIMITS.search_max)
    
    try:
        # Track search usage (only if private analytics available)
        track_tool_usage('search_memory', {
            'query_length': len(query),
            'limit': limit,
            'has_tags_filter': bool(tags_filter)
        })
        
        # Add timeout to prevent hanging
        return await asyncio.wait_for(_search_memory_unified_impl(query, supa_uid, client_name, limit, tags_filter), timeout=30.0)
    except asyncio.TimeoutError:
        return f"Search timed out. Please try a simpler query."
    except Exception as e:
        logging.error(f"Error in search_memory MCP tool: {e}", exc_info=True)
        return f"Error searching memory: {e}"


async def _search_memory_unified_impl(query: str, supa_uid: str, client_name: str, limit: int = 10, tags_filter: Optional[list[str]] = None) -> str:
    """Unified implementation that supports both basic search and tag filtering"""
    from app.utils.memory import get_async_memory_client
    memory_client = await get_async_memory_client()
    db = SessionLocal()
    
    try:
        # Get user (but don't filter by specific app - search ALL memories)
        user = get_or_create_user(db, supa_uid, None)
        
        # Check if user is trying to use Pro feature (tag filtering)
        if tags_filter and tags_filter:  # If tags_filter is provided and not empty
            try:
                SubscriptionChecker.check_pro_features(user, "advanced tag filtering")
            except Exception as e:
                return f"Error: {str(e)}"
        
        # 🚨 CRITICAL: Add user validation logging
        logger.info(f"🔍 SEARCH DEBUG - User ID: {supa_uid}, DB User ID: {user.id}, DB User user_id: {user.user_id}")
        
        # SECURITY CHECK: Verify user ID matches
        if user.user_id != supa_uid:
            logger.error(f"🚨 USER ID MISMATCH: Expected {supa_uid}, got {user.user_id}")
            return f"Error: User ID validation failed. Security issue detected."

        # We fetch a larger pool of results to filter from if a filter is applied
        fetch_limit = limit * 5 if tags_filter else limit

        # Call async memory client directly
        mem0_search_results = await memory_client.search(query=query, user_id=supa_uid, limit=fetch_limit)
        
        # 🚨 CRITICAL: Log the search results for debugging
        logger.info(f"🔍 SEARCH DEBUG - Query: {query}, Results count: {len(mem0_search_results.get('results', [])) if isinstance(mem0_search_results, dict) else len(mem0_search_results) if isinstance(mem0_search_results, list) else 0}")

        processed_results = []
        actual_results_list = []
        if isinstance(mem0_search_results, dict) and 'results' in mem0_search_results:
             actual_results_list = mem0_search_results['results']
        elif isinstance(mem0_search_results, list):
             actual_results_list = mem0_search_results

        if actual_results_list and tags_filter:
            logger.info(f"🔍 DEBUG: First result metadata: {actual_results_list[0].get('metadata')}")

        for mem_data in actual_results_list:
            # Skip if we've reached our limit
            if len(processed_results) >= limit:
                break
                
            mem0_id = mem_data.get('id')
            if not mem0_id: 
                continue
            
            # Apply tag filtering if requested
            if tags_filter:
                # Handle the metadata null case
                metadata = mem_data.get('metadata') or {}
                mem_tags = metadata.get('tags', [])
                
                # Only include if ALL specified tags are present
                if not all(tag in mem_tags for tag in tags_filter):
                    continue
            
            processed_results.append(mem_data)
        
        # 🚨 Log final results count
        logger.info(f"🔍 SEARCH FINAL - User {supa_uid}: {len(processed_results)} memories returned after filtering (tags_filter: {tags_filter})")
        
        return safe_json_dumps(processed_results)
    finally:
        db.close()


@mcp.tool(description="Search the user's memory, with optional tag filtering (V2).")
@retry_on_exception(retries=3, delay=1, backoff=2, exceptions=(ConnectionError,))
async def search_memory_v2(query: str, limit: int = None, tags_filter: Optional[list[str]] = None) -> str:
    """
    V2 search tool. Search user's memory with optional tag filtering.
    Returns memories that are semantically similar to the query.
    This is the recommended search tool for API key users.
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    if limit is None:
        limit = MEMORY_LIMITS.search_default
    limit = min(max(1, limit), MEMORY_LIMITS.search_max)
    
    try:
        # Track search v2 usage (only if private analytics available)
        track_tool_usage('search_memory_v2', {
            'query_length': len(query),
            'limit': limit,
            'has_tags_filter': bool(tags_filter)
        })
        
        return await asyncio.wait_for(_search_memory_v2_impl(query, supa_uid, client_name, limit, tags_filter), timeout=30.0)
    except asyncio.TimeoutError:
        return f"Search timed out. Please try a simpler query."
    except Exception as e:
        logging.error(f"Error in search_memory_v2 MCP tool: {e}", exc_info=True)
        return f"Error searching memory: {e}"

async def _search_memory_v2_impl(query: str, supa_uid: str, client_name: str, limit: int = 10, tags_filter: Optional[list[str]] = None) -> str:
    """Implementation of V2 search memory with post-fetch filtering."""
    from app.utils.memory import get_async_memory_client
    memory_client = await get_async_memory_client()
    
    # We fetch a larger pool of results to filter from if a filter is applied
    fetch_limit = limit * 5 if tags_filter else limit

    # Call async memory client directly
    mem0_search_results = await memory_client.search(query=query, user_id=supa_uid, limit=fetch_limit)
    
    actual_results_list = []
    if isinstance(mem0_search_results, dict) and 'results' in mem0_search_results:
         actual_results_list = mem0_search_results['results']
    elif isinstance(mem0_search_results, list):
         actual_results_list = mem0_search_results

    if actual_results_list:
        logger.info(f"🔍 DEBUG: Metadata of first result in _search_memory_v2_impl: {actual_results_list[0].get('metadata')}")

    # Perform filtering in our application code if a filter is provided
    if tags_filter:
        filtered_results = []
        for mem in actual_results_list:
            if len(filtered_results) >= limit:
                break
            
            # Robustly handle cases where metadata is missing or null.
            metadata = mem.get('metadata') or {}
            mem_tags = metadata.get('tags', [])
            if all(tag in mem_tags for tag in tags_filter):
                filtered_results.append(mem)
        processed_results = filtered_results
    else:
        processed_results = actual_results_list

    return safe_json_dumps(processed_results)


@mcp.tool(description="List all memories in the user's memory")
@retry_on_exception(retries=3, delay=1, backoff=2, exceptions=(ConnectionError,))
async def list_memories(limit: int = None) -> str:
    """
    List all memories for the user.
    Returns a formatted list of memories with their content and metadata.
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    # Use configured limits
    if limit is None:
        limit = MEMORY_LIMITS.list_default
    limit = min(max(1, limit), MEMORY_LIMITS.list_max)
    
    try:
        # Track list usage (only if private analytics available)
        track_tool_usage('list_memories', {'limit': limit})
        
        # Add timeout to prevent hanging
        return await asyncio.wait_for(_list_memories_impl(supa_uid, client_name, limit), timeout=30.0)
    except asyncio.TimeoutError:
        return f"List memories timed out. Please try again."
    except Exception as e:
        logging.error(f"Error in list_memories MCP tool: {e}", exc_info=True)
        return f"Error getting memories: {e}"


async def _list_memories_impl(supa_uid: str, client_name: str, limit: int = 20) -> str:
    """Implementation of list_memories with timeout protection"""
    from app.utils.memory import get_async_memory_client
    import time
    start_time = time.time()
    logger.info(f"list_memories: Starting for user {supa_uid}")

    memory_client = await get_async_memory_client()
    db = SessionLocal()
    try:
        # Get user (but don't filter by specific app - show ALL memories)
        user = get_or_create_user(db, supa_uid, None)
        
        # 🚨 CRITICAL: Add user validation logging
        logger.info(f"📋 LIST DEBUG - User ID: {supa_uid}, DB User ID: {user.id}, DB User user_id: {user.user_id}")
        
        # SECURITY CHECK: Verify user ID matches
        if user.user_id != supa_uid:
            logger.error(f"🚨 USER ID MISMATCH: Expected {supa_uid}, got {user.user_id}")
            return f"Error: User ID validation failed. Security issue detected."

        # Get ALL memories for this user across all apps with limit
        fetch_start_time = time.time()
        
        # Call async memory client directly
        all_mem0_memories = await memory_client.get_all(user_id=supa_uid, limit=limit)

        fetch_duration = time.time() - fetch_start_time
        
        results_count = len(all_mem0_memories.get('results', [])) if isinstance(all_mem0_memories, dict) else len(all_mem0_memories) if isinstance(all_mem0_memories, list) else 0
        logger.info(f"list_memories: mem0.get_all took {fetch_duration:.2f}s, found {results_count} results for user {supa_uid}")

        processed_results = []
        actual_results_list = []
        if isinstance(all_mem0_memories, dict) and 'results' in all_mem0_memories:
             actual_results_list = all_mem0_memories['results']
        elif isinstance(all_mem0_memories, list):
             actual_results_list = all_mem0_memories

        for mem_data in actual_results_list[:limit]:  # Extra safety to ensure limit
            mem0_id = mem_data.get('id')
            if not mem0_id: continue
            
            # 🚨 CRITICAL: Check if this memory belongs to the correct user
            memory_content = mem_data.get('memory', mem_data.get('content', ''))
            
            # Log suspicious content that might belong to other users
            if any(suspicious in memory_content.lower() for suspicious in ['pralayb', '/users/pralayb', 'faircopyfolder']):
                logger.error(f"🚨 SUSPICIOUS MEMORY DETECTED - User {supa_uid} got memory: {memory_content[:100]}...")
                logger.error(f"🚨 Memory metadata: {mem_data.get('metadata', {})}")
                continue  # Skip this memory
            
            processed_results.append(mem_data)
        
        # 🚨 Log final results count
        logger.info(f"📋 LIST FINAL - User {supa_uid}: {len(processed_results)} memories returned after filtering")
        
        json_start_time = time.time()
        response_json = safe_json_dumps(processed_results)
        json_duration = time.time() - json_start_time
        
        total_duration = time.time() - start_time
        logger.info(f"list_memories: Completed for user {supa_uid} in {total_duration:.2f}s (fetch: {fetch_duration:.2f}s, json: {json_duration:.2f}s)")
        
        return response_json
    finally:
        db.close()


@mcp.tool(description="Delete all memories in the user's memory")
async def delete_all_memories() -> str:
    """
    Delete all memories for the user. This action cannot be undone.
    Requires confirmation by being called explicitly.
    """
    from app.utils.memory import get_memory_client
    
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    memory_client = get_memory_client() # Initialize client when tool is called
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    try:
        # Track delete all usage (only if private analytics available)
        track_tool_usage('delete_all_memories', {})
        
        db = SessionLocal()
        try:
            from app.models import MemoryAccessLog
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
            
            return f"Successfully initiated deletion of all memories for user {supa_uid} via mem0 and updated SQL records."
        finally:
            db.close()
    except Exception as e:
        logging.error(f"Error in delete_all_memories MCP tool: {e}", exc_info=True)
        return f"Error deleting memories: {e}"


@mcp.tool(description="Get detailed information about a specific memory by its ID")
async def get_memory_details(memory_id: str) -> str:
    """
    Get detailed information about a specific memory, including all metadata.
    Use this to understand context about when and how a memory was created.
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    try:
        # Track memory details usage (only if private analytics available)
        track_tool_usage('get_memory_details', {'memory_id_length': len(memory_id)})
        
        # Add timeout to prevent hanging
        return await asyncio.wait_for(_get_memory_details_impl(memory_id, supa_uid, client_name), timeout=10.0)
    except asyncio.TimeoutError:
        return f"Memory lookup timed out. Try again or check if memory ID '{memory_id}' is correct."
    except Exception as e:
        logging.error(f"Error in get_memory_details MCP tool: {e}", exc_info=True)
        return f"Error retrieving memory details: {e}"


async def _get_memory_details_impl(memory_id: str, supa_uid: str, client_name: str) -> str:
    """Optimized implementation of get_memory_details"""
    from app.utils.memory import get_memory_client
    
    db = SessionLocal()
    try:
        # Get user quickly
        user = get_or_create_user(db, supa_uid, None)
        
        # First try SQL database (fastest)
        sql_memory = db.query(Memory).filter(
            Memory.id == memory_id,
            Memory.user_id == user.id,
            Memory.state != MemoryState.deleted
        ).first()
        
        if sql_memory:
            memory_details = {
                "id": str(sql_memory.id),
                "content": sql_memory.content,
                "created_at": sql_memory.created_at.isoformat() if sql_memory.created_at else None,
                "updated_at": sql_memory.updated_at.isoformat() if sql_memory.updated_at else None,
                "state": sql_memory.state.value if sql_memory.state else None,
                "metadata": sql_memory.metadata_ or {},
                "app_name": sql_memory.app.name if sql_memory.app else None,
                "categories": [cat.name for cat in sql_memory.categories] if sql_memory.categories else [],
                "source": "sql_database"
            }
            return safe_json_dumps(memory_details, indent=2)
        
        # Try mem0 with direct search instead of getting all memories
        memory_client = get_memory_client()
        
        # Use search with the exact ID as query - much faster than get_all()
        search_result = memory_client.search(query=memory_id, user_id=supa_uid, limit=20)
        
        memories_list = []
        if isinstance(search_result, dict) and 'results' in search_result:
            memories_list = search_result['results']
        elif isinstance(search_result, list):
            memories_list = search_result
        
        # Look for exact ID match
        for mem in memories_list:
            if isinstance(mem, dict) and mem.get('id') == memory_id:
                return safe_json_dumps({
                    "id": mem.get('id'),
                    "content": mem.get('memory', mem.get('content', 'No content available')),
                    "metadata": mem.get('metadata', {}),
                    "created_at": mem.get('created_at'),
                    "updated_at": mem.get('updated_at'),
                    "score": mem.get('score'),
                    "source": "mem0_vector_store"
                }, indent=2)
        
        return f"Memory with ID '{memory_id}' not found. Possible reasons:\n1. Memory doesn't exist\n2. Belongs to different user\n3. Has been deleted\n4. ID format incorrect"
        
    finally:
        db.close()


@mcp.tool(description="Fast memory search for simple questions - try this first before using heavier tools")
async def ask_memory(question: str) -> str:
    """
    Fast memory search for simple questions about the user.
    This searches stored memories only (not full documents) and returns quick, conversational answers.
    Perfect for everyday questions like "What are my preferences?" or "What do you know about me?"
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)

    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"

    try:
        # Track usage (only if private analytics available)
        track_tool_usage('ask_memory', {'query_length': len(question)})
        
        # Lightweight version for better performance
        return await _lightweight_ask_memory_impl(question, supa_uid, client_name)
    except Exception as e:
        logger.error(f"Error in ask_memory: {e}", exc_info=True)
        return f"I had trouble processing your question: {str(e)}. Try rephrasing or use 'search_memory' for simpler queries."


async def _lightweight_ask_memory_impl(question: str, supa_uid: str, client_name: str) -> str:
    """Lightweight ask_memory implementation for quick answers"""
    from app.utils.memory import get_async_memory_client
    from mem0.llms.openai import OpenAILLM
    from mem0.configs.llms.base import BaseLlmConfig
    
    import time
    start_time = time.time()
    logger.info(f"ask_memory: Starting for user {supa_uid}")
    
    try:
        db = SessionLocal()
        try:
            # Get user quickly
            user = get_or_create_user(db, supa_uid, None)
            
            # SECURITY CHECK: Verify user ID matches
            if user.user_id != supa_uid:
                logger.error(f"🚨 USER ID MISMATCH: Expected {supa_uid}, got {user.user_id}")
                return f"Error: User ID validation failed. Security issue detected."

            # Initialize services
            memory_client = await get_async_memory_client()
            llm = OpenAILLM(config=BaseLlmConfig(model="gpt-4o-mini"))
            
            # 1. Quick memory search (limit to 10 for speed)
            search_start_time = time.time()
            logger.info(f"ask_memory: Starting memory search for user {supa_uid}")
            
            # Call async memory client directly
            search_result = await memory_client.search(query=question, user_id=supa_uid, limit=10)

            search_duration = time.time() - search_start_time
            
            # Process results
            memories = []
            if isinstance(search_result, dict) and 'results' in search_result:
                memories = search_result['results'][:10]
            elif isinstance(search_result, list):
                memories = search_result[:10]
            
            logger.info(f"ask_memory: Memory search for user {supa_uid} took {search_duration:.2f}s. Found {len(memories)} results.")
            
            # Filter out contaminated memories and limit token usage
            clean_memories = []
            total_chars = 0
            max_chars = 8000  # Conservative limit to avoid token issues
            
            for idx, mem in enumerate(memories):
                memory_text = mem.get('memory', mem.get('content', ''))
                memory_line = f"Memory {idx+1}: {memory_text}"
                
                # Stop adding memories if we're approaching token limits
                if total_chars + len(memory_line) > max_chars:
                    break
                    
                clean_memories.append(memory_line)
                total_chars += len(memory_line)
            
            # Use LLM for fast, cheap synthesis with safer prompt
            prompt = f"""You are an AI assistant answering a question about someone's personal memories. Always address them directly as "you" (never "the user" or third person).
            
            Their memories:
            {chr(10).join(clean_memories)}
            
            Their question: {question}
            
            Answer their question based only on their memories. Address them directly as "you" in your response."""
            
            try:
                llm_start_time = time.time()
                logger.info(f"ask_memory: Starting LLM call for user {supa_uid}")
                
                # Enforce a 25-second timeout on the LLM call and run it in a separate thread
                loop = asyncio.get_running_loop()
                llm_call = functools.partial(llm.generate_response, [{"role": "user", "content": prompt}])
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, llm_call),
                    timeout=25.0
                )

                llm_duration = time.time() - llm_start_time
                logger.info(f"ask_memory: LLM call for user {supa_uid} took {llm_duration:.2f}s")
                # Access response.text safely
                result = response
                total_duration = time.time() - start_time
                
                # Only include timing info for non-SMS clients (for debugging)
                current_client = client_name_var.get(None)
                if current_client != "sms":
                    result += f"\n\n💡 Timings: search={search_duration:.2f}s, llm={llm_duration:.2f}s, total={total_duration:.2f}s | {len(clean_memories)} memories"
                
                return result
            except asyncio.TimeoutError:
                logger.error(f"LLM call for ask_memory timed out after 25s for user {supa_uid}.")
                return "I'm sorry, my connection to my thinking process was interrupted. Please try again."
            except ValueError as e:
                # Handle cases where the response is blocked or has no content
                if "finish_reason" in str(e):
                    logger.error(f"LLM response for ask_memory was blocked or invalid. Query: '{question}'. Error: {e}")
                    return "The response to your question could not be generated, possibly due to safety filters or an invalid request. Please try rephrasing your question."
                else:
                    logger.error(f"Error processing LLM response in ask_memory: {e}", exc_info=True)
                    return f"An error occurred while generating the response: {e}"
            except Exception as e:
                logger.error(f"Error in lightweight ask_memory: {e}", exc_info=True)
                return f"An unexpected error occurred in ask_memory: {e}"
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in lightweight ask_memory: {e}", exc_info=True)
        total_duration = time.time() - start_time
        logger.error(f"ask_memory: Failed after {total_duration:.2f}s for user {supa_uid}")
        return f"An unexpected error occurred in ask_memory: {e}"


@mcp.tool(description="Advanced memory search (temporarily disabled for stability)")
async def smart_memory_query(search_query: str) -> str:
    """
    Advanced memory search temporarily disabled due to performance issues.
    Use deep_memory_query or search_memory instead.
    """
    return "⚠️ Smart memory query is temporarily disabled for stability. Please use 'search_memory' or 'deep_memory_query' instead." 