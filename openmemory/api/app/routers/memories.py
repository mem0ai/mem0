import datetime
import hashlib
import logging
# Python 3.10 compatibility for datetime.UTC
try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc
from typing import List, Optional, Set, Dict, Any
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from sqlalchemy import or_, func

from app.database import get_db
from app.auth import get_current_supa_user
from gotrue.types import User as SupabaseUser
# Memory clients are imported in individual functions where needed
from app.utils.db import get_or_create_user, get_user_and_app
from app.models import (
    Memory, MemoryState, MemoryAccessLog, App,
    MemoryStatusHistory, User, Category, AccessControl, UserNarrative
)
from app.schemas import MemoryResponse, PaginatedMemoryResponse
from app.utils.permissions import check_memory_access_permissions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/memories", tags=["memories"])

# Create a dummy app UUID for Jean Memory V2 memories
JEAN_MEMORY_V2_APP_ID = UUID("00000000-0000-0000-0000-000000000001")


def get_memory_or_404(db: Session, memory_id: UUID, user_id: UUID) -> Memory:
    memory = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user_id).first()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found or you do not have permission")
    return memory


def update_memory_state(db: Session, memory_id: UUID, new_state: MemoryState, changed_by_user_id: UUID):
    memory = get_memory_or_404(db, memory_id, changed_by_user_id)
    
    old_state = memory.state
    memory.state = new_state
    if new_state == MemoryState.archived:
        memory.archived_at = datetime.datetime.now(UTC)
    elif new_state == MemoryState.deleted:
        memory.deleted_at = datetime.datetime.now(UTC)

    history = MemoryStatusHistory(
        memory_id=memory_id,
        changed_by=changed_by_user_id,
        old_state=old_state,
        new_state=new_state
    )
    db.add(history)


def get_accessible_memory_ids(db: Session, app_id: UUID) -> Set[UUID]:
    """
    Get the set of memory IDs that the app has access to based on app-level ACL rules.
    Returns all memory IDs if no specific restrictions are found.
    """
    # Get app-level access controls
    app_access = db.query(AccessControl).filter(
        AccessControl.subject_type == "app",
        AccessControl.subject_id == app_id,
        AccessControl.object_type == "memory"
    ).all()

    # If no app-level rules exist, return None to indicate all memories are accessible
    if not app_access:
        return None

    # Initialize sets for allowed and denied memory IDs
    allowed_memory_ids = set()
    denied_memory_ids = set()

    # Process app-level rules
    for rule in app_access:
        if rule.effect == "allow":
            if rule.object_id:  # Specific memory access
                allowed_memory_ids.add(rule.object_id)
            else:  # All memories access
                return None  # All memories allowed
        elif rule.effect == "deny":
            if rule.object_id:  # Specific memory denied
                denied_memory_ids.add(rule.object_id)
            else:  # All memories denied
                return set()  # No memories accessible

    # Remove denied memories from allowed set
    if allowed_memory_ids:
        allowed_memory_ids -= denied_memory_ids

    return allowed_memory_ids


# List all memories with filtering (no pagination)
@router.get("/", response_model=List[MemoryResponse])
async def list_memories(
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    app_id: Optional[UUID] = None,
    from_date: Optional[int] = Query(
        None,
        description="Filter memories created after this date (timestamp)",
        examples=[1718505600]
    ),
    to_date: Optional[int] = Query(
        None,
        description="Filter memories created before this date (timestamp)",
        examples=[1718505600]
    ),
    categories: Optional[str] = None,
    search_query: Optional[str] = None,
    sort_column: Optional[str] = Query(None, description="Column to sort by (memory, categories, app_name, created_at)"),
    sort_direction: Optional[str] = Query(None, description="Sort direction (asc or desc)"),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found or could not be created")

    # Build base query for SQL memories
    query = db.query(Memory).filter(
        Memory.user_id == user.id,
        Memory.state != MemoryState.deleted,
        Memory.state != MemoryState.archived,
        Memory.content.ilike(f"%{search_query}%") if search_query else True
    )

    # Apply filters
    if app_id:
        query = query.filter(Memory.app_id == app_id)

    if from_date:
        from_datetime = datetime.datetime.fromtimestamp(from_date, tz=UTC)
        query = query.filter(Memory.created_at >= from_datetime)

    if to_date:
        to_datetime = datetime.datetime.fromtimestamp(to_date, tz=UTC)
        query = query.filter(Memory.created_at <= to_datetime)

    # Add joins for app and categories after filtering
    query = query.outerjoin(App, Memory.app_id == App.id)
    query = query.outerjoin(Memory.categories)

    # Apply category filter if provided
    if categories:
        category_list = [c.strip() for c in categories.split(",")]
        query = query.filter(Category.name.in_(category_list))
    
    # Apply sorting if specified
    if sort_column:
        sort_field = None
        if sort_column == "memory": sort_field = Memory.content
        elif sort_column == "categories": sort_field = Category.name
        elif sort_column == "app_name": sort_field = App.name
        elif sort_column == "created_at": sort_field = Memory.created_at
        
        if sort_field is not None:
            if sort_column == "categories" and not categories:
                query = query.join(Memory.categories)
            if sort_column == "app_name" and not app_id:
                query = query.outerjoin(App, Memory.app_id == App.id)
                
            if sort_direction == "desc":
                query = query.order_by(sort_field.desc())
            else:
                query = query.order_by(sort_field.asc())
        else:
            query = query.order_by(Memory.created_at.desc())
    else:
        query = query.order_by(Memory.created_at.desc())

    # Get ALL SQL memories (no pagination)
    sql_memories = query.options(joinedload(Memory.app), joinedload(Memory.categories)).all()
    
    # Filter SQL results based on permissions
    permitted_sql_memories = []
    for item in sql_memories:
        if check_memory_access_permissions(db, item, app_id):
            permitted_sql_memories.append(item)

    # Transform SQL memories to response format
    sql_response_items = [
        MemoryResponse(
            id=mem.id,
            content=mem.content,
            created_at=mem.created_at, 
            state=mem.state.value if mem.state else None,
            app_id=mem.app_id,
            app_name=mem.app.name if mem.app else "Unknown App", 
            categories=[cat.name for cat in mem.categories], 
            metadata_=mem.metadata_
        )
        for mem in permitted_sql_memories
    ]
    
    # Also fetch ALL memories from Jean Memory V2 (no pagination)
    jean_response_items = []
    try:
        from app.utils.memory import get_async_memory_client
        memory_client = await get_async_memory_client()
        
        # Use search query if provided, otherwise get recent memories
        jean_query = search_query if search_query else "memories"
        # Get ALL memories from Jean Memory V2 (increase limit significantly)
        jean_limit = 1000  # Large limit to get all memories
        
        jean_results = await memory_client.search(
            query=jean_query,
            user_id=supabase_user_id_str,
            limit=jean_limit
        )
        
        # Process Jean Memory V2 results
        jean_memories = []
        if isinstance(jean_results, dict) and 'results' in jean_results:
            jean_memories = jean_results['results']
        elif isinstance(jean_results, list):
            jean_memories = jean_results
        
        # Convert Jean Memory V2 results to response format
        # ONLY INCLUDE ACTUAL USER MEMORIES - Filter out graph-derived content
        for idx, jean_mem in enumerate(jean_memories):
            try:
                # Extract fields with fallbacks
                memory_content = jean_mem.get('memory', jean_mem.get('content', ''))
                metadata = jean_mem.get('metadata', {})
                
                # FILTER OUT INVALID MEMORIES - Skip search terms and garbage
                if not memory_content or not isinstance(memory_content, str):
                    continue
                
                memory_content = memory_content.strip()
                
                # Skip obvious invalid data (but allow all valid user memories)
                if not memory_content.strip():
                    continue
                
                # ONLY INCLUDE MEMORIES FROM USER SOURCES (not graph-derived)
                # Check metadata to see if this is a real user memory vs graph-generated content
                source_app = metadata.get('app_name', '')
                created_via = metadata.get('created_via', '')
                
                # FIXED: Allow Jean Memory V2 memories through - they are user memories with ontology enhancement
                # Skip if this looks like graph-derived content rather than user input
                if (source_app.lower() in ['system', 'auto_generated'] or
                    created_via.lower() in ['auto', 'system_generated']):
                    logger.info(f"🚫 Skipping auto-generated content: '{memory_content[:30]}...'")
                    continue
                    
                # ALLOW Jean Memory V2 and jean memory through - these are enhanced user memories
                if 'jean memory' in source_app.lower():
                    logger.info(f"✅ Including Jean Memory V2 enhanced memory: '{memory_content[:30]}...'")
                    pass  # Allow it through
                
                # Skip very short content that's likely not a real memory
                if len(memory_content) < 10:
                    logger.info(f"🚫 Skipping too short: '{memory_content}'")
                    continue
                
                # Generate a proper UUID for Jean Memory V2 results
                memory_id_raw = jean_mem.get('id', f'jean_v2_{idx}')
                if isinstance(memory_id_raw, str) and not memory_id_raw.startswith('jean_v2_'):
                    # Try to parse as UUID first
                    try:
                        memory_id = UUID(memory_id_raw)
                    except ValueError:
                        # Generate a deterministic UUID based on content
                        content_hash = hashlib.md5(f"{supabase_user_id_str}_{memory_content}_{idx}".encode()).hexdigest()
                        memory_id = UUID(content_hash[:32].ljust(32, '0'))
                else:
                    # Generate a new UUID for Jean Memory V2 results
                    memory_id = uuid4()
                
                created_at = jean_mem.get('created_at')
                metadata = jean_mem.get('metadata', {})
                
                # Parse created_at if it's a string
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    except:
                        created_at = datetime.datetime.now(UTC)
                elif not created_at:
                    created_at = datetime.datetime.now(UTC)
                
                # Get app info from metadata
                app_name = metadata.get('app_name', 'Jean Memory V2')
                
                jean_response_item = MemoryResponse(
                    id=memory_id,
                    content=memory_content,
                    created_at=created_at,
                    state='active',  # Jean Memory V2 memories are active
                    app_id=JEAN_MEMORY_V2_APP_ID,  # Use dummy app ID for validation
                    app_name=app_name,
                    categories=[],  # Categories could be extracted from metadata if needed
                    metadata_=metadata
                )
                jean_response_items.append(jean_response_item)
                logger.info(f"✅ Added valid Jean Memory V2 result: '{memory_content[:50]}...'")
                
            except Exception as e:
                logger.error(f"Error processing Jean Memory V2 result: {e}")
                continue
        
        logger.info(f"✅ Retrieved {len(jean_response_items)} Jean Memory V2 memories")
        
    except Exception as e:
        logger.error(f"⚠️ Failed to fetch from Jean Memory V2: {e}")
        logger.info("✅ Using SQL memories only")

    # Combine ALL results (no pagination)
    all_response_items = sql_response_items + jean_response_items
    
    # Sort combined results by created_at desc (most recent first)
    all_response_items.sort(key=lambda x: x.created_at, reverse=True)
    
    logger.info(f"✅ Retrieved {len(sql_response_items)} SQL + {len(jean_response_items)} Jean Memory V2 memories")
    logger.info(f"📊 Total memories: {len(all_response_items)}")

    return all_response_items


# Get all categories
@router.get("/categories")
async def get_categories(
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    memories = db.query(Memory).filter(Memory.user_id == user.id, Memory.state != MemoryState.deleted, Memory.state != MemoryState.archived).all()
    categories_set = set()
    for memory_item in memories:
        for category_item in memory_item.categories:
            categories_set.add(category_item.name)
    
    return {
        "categories": list(categories_set),
        "total": len(categories_set)
    }


# Get or generate user narrative using Jean Memory V2.
@router.get("/narrative")
async def get_user_narrative(
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    """
    Get or generate user narrative using Jean Memory V2.
    Returns cached narrative if fresh, otherwise generates new one using Jean Memory V2.
    """
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check for existing cached narrative
    narrative = db.query(UserNarrative).filter(UserNarrative.user_id == user.id).first()
    
    # Check if narrative is fresh (within 7 days) - TEMPORARILY DISABLED FOR DEBUG
    if False and narrative:  # <-- Disabled to force regeneration
        now = datetime.datetime.now(narrative.generated_at.tzinfo or UTC)
        age_days = (now - narrative.generated_at).days
        
        if age_days <= 7:  # Narrative is still fresh
            return {
                "narrative": narrative.narrative_content,
                "generated_at": narrative.generated_at,
                "version": narrative.version,
                "age_days": age_days,
                "source": "cached"
            }
    
    # Generate new narrative using Jean Memory V2
    try:
        from app.utils.memory import get_async_memory_client
        memory_client = await get_async_memory_client()
        
        # Get comprehensive memories from Jean Memory V2
        logger.info(f"🔍 NARRATIVE DEBUG: Starting memory search for user {supabase_user_id_str}")
        
        memory_results = await memory_client.search(
            query="life experiences preferences goals work interests personality",
            user_id=supabase_user_id_str,
            limit=50
        )
        
        logger.info(f"🔍 NARRATIVE DEBUG: Raw search results type: {type(memory_results)}")
        logger.info(f"🔍 NARRATIVE DEBUG: Raw search results: {memory_results}")
        
        # Process memory results with PROPER FILTERING
        memories_text = []
        if isinstance(memory_results, dict) and 'results' in memory_results:
            memories = memory_results['results']
            logger.info(f"🔍 NARRATIVE DEBUG: Extracted {len(memories)} memories from dict results")
        elif isinstance(memory_results, list):
            memories = memory_results
            logger.info(f"🔍 NARRATIVE DEBUG: Using list of {len(memories)} memories directly")
        else:
            memories = []
            logger.warning(f"🔍 NARRATIVE DEBUG: No memories found - unexpected result type")
        
        # Filter for narrative generation (less aggressive - include all meaningful content)
        for mem in memories[:25]:  # Limit for narrative generation
            content = mem.get('memory', mem.get('content', ''))
            
            if not content or not isinstance(content, str):
                continue
            
            content = content.strip()
            
            # Skip empty content
            if not content.strip():
                continue
            
            # Skip very short content 
            if len(content) < 5:
                logger.info(f"🚫 Narrative: Skipping too short: '{content}'")
                continue
            
            # Include ALL other content (both user memories and graph insights)
            memories_text.append(content)
            logger.info(f"✅ Narrative: Added content: '{content[:50]}...'")
        
        logger.info(f"📊 Narrative: Found {len(memories_text)} pieces of content for narrative generation")
        
        if not memories_text:
            # Return a helpful message instead of raising an error
            return {
                "narrative": "You have no memories! Please add some to see your Life Narrative.",
                "generated_at": datetime.datetime.now(UTC),
                "version": "empty",
                "age_days": 0,
                "source": "generated",
                "memory_count": 0
            }
        
        # Generate narrative using Gemini (same as MCP orchestration)
        from app.utils.gemini import GeminiService
        
        gemini = GeminiService()
        combined_text = "\n".join(memories_text)
        
        logger.info(f"🧠 NARRATIVE DEBUG: Sending {len(combined_text)} characters to Gemini Pro")
        logger.info(f"🧠 NARRATIVE DEBUG: Combined text preview: '{combined_text[:200]}...'")
        
        narrative_content = await gemini.generate_narrative_pro(combined_text)
        
        logger.info(f"🧠 NARRATIVE DEBUG: Generated narrative length: {len(narrative_content)} characters")
        logger.info(f"🧠 NARRATIVE DEBUG: Narrative preview: '{narrative_content[:200]}...'")
        
        
        # Cache the new narrative
        if narrative:
            # Update existing
            narrative.narrative_content = narrative_content
            narrative.generated_at = datetime.datetime.now(UTC)
            narrative.version += 1
        else:
            # Create new
            narrative = UserNarrative(
                user_id=user.id,
                narrative_content=narrative_content,
                generated_at=datetime.datetime.now(UTC),
                version=1
            )
            db.add(narrative)
        
        db.commit()
        db.refresh(narrative)
        
        logger.info(f"✅ Generated new narrative for user {supabase_user_id_str} using Jean Memory V2")
        
        return {
            "narrative": narrative.narrative_content,
            "generated_at": narrative.generated_at,
            "version": narrative.version,
            "age_days": 0,
            "source": "jean_memory_v2",
            "memory_count": len(memories_text)
        }
        
    except Exception as e:
        logger.error(f"Failed to generate narrative using Jean Memory V2: {e}")
        
        # Handle specific "Insufficient memories" error gracefully
        if "Insufficient memories" in str(e) or "204" in str(e):
            memory_count = len(memories_text) if 'memories_text' in locals() else 0
            if memory_count > 0:
                return {
                    "narrative": f"You have {memory_count} memories, but need more for a comprehensive Life Narrative. Keep adding memories to unlock richer insights!",
                    "generated_at": datetime.datetime.now(UTC),
                    "version": "insufficient",
                    "age_days": 0,
                    "source": "generated",
                    "memory_count": memory_count
                }
            else:
                return {
                    "narrative": "You have no memories! Please add some to see your Life Narrative.",
                    "generated_at": datetime.datetime.now(UTC),
                    "version": "empty",
                    "age_days": 0,
                    "source": "generated",
                    "memory_count": 0
                }
        
        # Fallback to cached narrative if available
        if narrative:
            return {
                "narrative": narrative.narrative_content,
                "generated_at": narrative.generated_at,
                "version": narrative.version,
                "age_days": (datetime.datetime.now(UTC) - narrative.generated_at).days,
                "source": "cached_fallback",
                "error": str(e)
            }
        else:
            # Final fallback for any other errors
            return {
                "narrative": "Unable to generate your Life Narrative right now. Please try again later or add more memories.",
                "generated_at": datetime.datetime.now(UTC),
                "version": "error",
                "age_days": 0,
                "source": "error_fallback",
                "error": str(e)
            }


class CreateMemoryRequestData(BaseModel):
    text: str
    metadata: dict = {}
    infer: bool = True
    app_name: str


# Create new memory
@router.post("/", response_model=MemoryResponse)
async def create_memory(
    request: CreateMemoryRequestData,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    
    user, app_obj = get_user_and_app(db, supabase_user_id_str, request.app_name, current_supa_user.email)

    if not app_obj.is_active:
        raise HTTPException(status_code=403, detail=f"App {request.app_name} is currently paused. Cannot create new memories.")

    # 1. Save to SQL database (existing behavior)
    sql_memory = Memory(
        user_id=user.id,
        app_id=app_obj.id,
        content=request.text,
        metadata_=request.metadata,
        created_at=datetime.datetime.now(UTC)
    )
    db.add(sql_memory)
    try:
        db.commit()
        db.refresh(sql_memory)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    # 2. Also save to Jean Memory V2 (NEW: dual storage)
    try:
        from app.utils.memory import get_async_memory_client
        memory_client = await get_async_memory_client()
        
        # Prepare metadata for Jean Memory V2
        jean_metadata = {
            'app_name': request.app_name,
            'app_id': str(app_obj.id),
            'sql_memory_id': str(sql_memory.id),
            'created_via': 'rest_api'
        }
        if request.metadata:
            jean_metadata.update(request.metadata)
        
        # Add to Jean Memory V2 (async)
        logger.info(f"🔍 DEBUG: About to add memory to Jean Memory V2:")
        logger.info(f"   User ID: {supabase_user_id_str}")
        logger.info(f"   Content: '{request.text}'")
        logger.info(f"   Metadata: {jean_metadata}")
        
        jean_result = await memory_client.add(
            messages=request.text,
            user_id=supabase_user_id_str,
            metadata=jean_metadata
        )
        
        logger.info(f"🔍 DEBUG: Jean Memory V2 add result: {jean_result}")
        logger.info(f"✅ Memory {sql_memory.id} stored in both SQL and Jean Memory V2")
        
    except Exception as e:
        # Log error but don't fail the request - SQL memory is primary
        logger.error(f"⚠️ Failed to store memory in Jean Memory V2: {e}")
        logger.info("✅ Memory saved to SQL database successfully")

    return MemoryResponse(
        id=sql_memory.id,
        content=sql_memory.content,
        created_at=sql_memory.created_at,
        state=sql_memory.state.value if sql_memory.state else None,
        app_id=sql_memory.app_id,
        app_name=app_obj.name,
        categories=[cat.name for cat in sql_memory.categories],
        metadata_=sql_memory.metadata_
    )


# IMPORTANT: Specific routes must come before general routes
# Life Graph Data endpoint - must be before /{memory_id}
@router.get("/life-graph-data")
async def get_life_graph_data(
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    limit: int = Query(50, description="Maximum number of memories to analyze"),
    focus_query: Optional[str] = Query(None, description="Optional query to focus the graph on specific topics"),
    use_cache: bool = Query(True, description="Whether to use cached data"),
    include_entities: bool = Query(True, description="Whether to extract entities from memories"),
    include_temporal_clusters: bool = Query(True, description="Whether to create temporal clusters"),
    db: Session = Depends(get_db)
):
    """
    Get optimized life graph data for visualization using the same approach as Deep Life Query.
    
    This endpoint provides:
    1. Memory nodes with entity extraction
    2. Relationships between memories  
    3. Clustering information for visualization
    4. Cached for performance
    5. Uses the WORKING memory client approach (same as Deep Life Query)
    """
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    
    try:
        # Check cache first if enabled
        if use_cache:
            from app.utils.graph_cache import get_cached_graph_data
            cached_data = get_cached_graph_data(
                user_id=supabase_user_id_str,
                query=focus_query,
                limit=limit,
                max_age_minutes=30
            )
            
            if cached_data:
                logger.info(f"🚀 Returning cached life graph data for user {supabase_user_id_str}")
                return cached_data
        
        # Use the SAME memory client approach as Deep Life Query (which works!)
        from app.utils.memory import get_async_memory_client
        memory_client = await get_async_memory_client()
        
        logger.info(f"🚀 Generating life graph data using WORKING memory client for user {supabase_user_id_str}")
        
        # Use enhanced search query based on focus or comprehensive overview
        search_query = focus_query if focus_query else "comprehensive life overview experiences relationships growth"
        
        # Get memories using the WORKING approach (same as Deep Life Query)
        memory_results = await memory_client.search(
            query=search_query,
            user_id=supabase_user_id_str,
            limit=limit
        )
        
        # Process memory results (same as Deep Life Query)
        memories = []
        if isinstance(memory_results, dict) and 'results' in memory_results:
            memories = memory_results['results']
        elif isinstance(memory_results, list):
            memories = memory_results
        
        logger.info(f"📊 Retrieved {len(memories)} memories for life graph")
        
        # Process memories for visualization
        processed_memories = []
        for i, mem in enumerate(memories):
            content = mem.get('memory', mem.get('content', ''))
            metadata = mem.get('metadata', {})
            
            if not content or len(content.strip()) < 5:
                continue
            
            processed_memories.append({
                'id': mem.get('id', f'mem_{i}'),
                'content': content.strip(),
                'metadata': metadata,
                'created_at': mem.get('created_at'),
                'source': metadata.get('app_name', 'Jean Memory V2')
            })
        
        # Create visualization data using working approach
        from jean_memory_v2.search import _create_life_graph_visualization_data
        
        visualization_data = await _create_life_graph_visualization_data(
            processed_memories,
            include_entities=include_entities,
            include_temporal_clusters=include_temporal_clusters,
            synthesis=""  # No synthesis needed for now
        )
        
        # Add enhanced metadata
        visualization_data['metadata'].update({
            'search_method': 'working_memory_client',
            'capabilities_used': {
                'mem0_semantic_search': True,
                'graphiti_graph_search': False,  # Not using direct Graphiti
                'gemini_ai_synthesis': False,    # Not using AI synthesis yet
                'temporal_pattern_analysis': include_temporal_clusters,
                'relationship_mapping': True
            },
            'enhanced_entities_extracted': len([n for n in visualization_data['nodes'] if n.get('type') == 'entity']),
            'temporal_patterns_identified': len([n for n in visualization_data['nodes'] if n.get('type') == 'temporal_pattern']),
            'ai_insights': []
        })
        
        # Cache the results if caching is enabled
        if use_cache:
            from app.utils.graph_cache import cache_graph_data
            cache_graph_data(
                user_id=supabase_user_id_str,
                query=focus_query,
                limit=limit,
                data=visualization_data
            )
        
        logger.info(f"✅ Life graph data generated successfully: {len(visualization_data['nodes'])} nodes, {len(visualization_data['edges'])} edges")
        
        return visualization_data
        
    except Exception as e:
        logger.error(f"Life Graph Data failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Life graph data generation failed: {str(e)}"
        )


# Get memory by ID
@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: UUID,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)

    # First, try to get from SQL database (main memories)
    sql_memory = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user.id).first()
    
    if sql_memory:
        # Found in SQL database - return it
        return MemoryResponse(
            id=sql_memory.id,
            content=sql_memory.content,
            created_at=sql_memory.created_at,
            state=sql_memory.state.value if sql_memory.state else None,
            app_id=sql_memory.app_id,
            app_name=sql_memory.app.name if sql_memory.app else "Unknown App",
            categories=[category.name for category in sql_memory.categories],
            metadata_=sql_memory.metadata_
        )
    
    # Not found in SQL, try Jean Memory V2 (submemories)
    try:
        from app.utils.memory import get_async_memory_client
        memory_client = await get_async_memory_client()
        
        # Search broadly in Jean Memory V2 since ID-based search might not work
        jean_results = await memory_client.search(
            query="memories",  # Broad search to get all memories
            user_id=supabase_user_id_str,
            limit=1000  # Large limit to ensure we get all memories
        )
        
        # Process Jean Memory V2 results to find matching ID
        jean_memories = []
        if isinstance(jean_results, dict) and 'results' in jean_results:
            jean_memories = jean_results['results']
        elif isinstance(jean_results, list):
            jean_memories = jean_results
        
        # Look for memory with matching ID
        for jean_mem in jean_memories:
            jean_memory_id = jean_mem.get('id')
            
            # Check if this is the memory we're looking for (try both string and UUID comparison)
            if (str(jean_memory_id) == str(memory_id) or 
                jean_memory_id == memory_id or
                (isinstance(jean_memory_id, str) and jean_memory_id.replace('-', '') == str(memory_id).replace('-', ''))):
                
                memory_content = jean_mem.get('memory', jean_mem.get('content', ''))
                metadata = jean_mem.get('metadata', {})
                created_at = jean_mem.get('created_at')
                
                # Skip if no content
                if not memory_content or not memory_content.strip():
                    continue
                
                # Parse created_at if it's a string
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    except:
                        created_at = datetime.datetime.now(UTC)
                elif not created_at:
                    created_at = datetime.datetime.now(UTC)
                
                # Get app info from metadata
                app_name = metadata.get('app_name', 'Jean Memory V2')
                
                logger.info(f"✅ Found memory {memory_id} in Jean Memory V2: '{memory_content[:50]}...'")
                
                return MemoryResponse(
                    id=memory_id,
                    content=memory_content,
                    created_at=created_at,
                    state='active',  # Jean Memory V2 memories are active
                    app_id=JEAN_MEMORY_V2_APP_ID,  # Use dummy app ID
                    app_name=app_name,
                    categories=[],  # Submemories have empty categories
                    metadata_=metadata
                )
        
        logger.info(f"Memory {memory_id} not found in Jean Memory V2 either")
        
    except Exception as e:
        logger.warning(f"Failed to search Jean Memory V2 for memory {memory_id}: {e}")
    
    # Memory not found in either system
    raise HTTPException(status_code=404, detail="Memory not found or you do not have permission")


class DeleteMemoriesRequestData(BaseModel):
    memory_ids: List[UUID]


# Delete multiple memories
@router.delete("/", status_code=200)
async def delete_memories(
    request: DeleteMemoriesRequestData,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)

    deleted_count = 0
    not_found_count = 0
    jean_deleted_count = 0

    # Also prepare to delete from Jean Memory V2
    memory_client = None
    try:
        from app.utils.memory import get_async_memory_client
        memory_client = await get_async_memory_client()
    except Exception as e:
        logger.error(f"Failed to initialize Jean Memory V2 client for deletion: {e}")

    for memory_id_to_delete in request.memory_ids:
        try:
            # 1. Delete from SQL database (existing behavior)
            update_memory_state(db, memory_id_to_delete, MemoryState.deleted, user.id)
            deleted_count += 1
            
            # 2. Also try to delete from Jean Memory V2 (NEW: dual deletion)
            if memory_client:
                try:
                    jean_result = await memory_client.delete(
                        memory_id=str(memory_id_to_delete),
                        user_id=supabase_user_id_str
                    )
                    if jean_result and jean_result.get('message'):
                        jean_deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete memory {memory_id_to_delete} from Jean Memory V2: {e}")
                    # Don't fail the whole operation if Jean Memory V2 deletion fails
            
        except HTTPException as e:
            if e.status_code == 404:
                not_found_count += 1
            else:
                raise e # Re-raise other exceptions
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error committing deletions: {e}")

    # Enhanced response with dual system info
    message = f"Successfully deleted {deleted_count} memories from SQL database"
    if jean_deleted_count > 0:
        message += f" and {jean_deleted_count} from Jean Memory V2"
    if not_found_count > 0:
        message += f". Not found: {not_found_count}"
    
    logger.info(f"✅ Deleted {deleted_count} SQL + {jean_deleted_count} Jean Memory V2 memories")
    
    return {"message": message}


# Archive memories
@router.post("/actions/archive", status_code=200)
async def archive_memories(
    memory_ids: List[UUID],
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    archived_count = 0
    not_found_count = 0

    for memory_id_to_archive in memory_ids:
        try:
            update_memory_state(db, memory_id_to_archive, MemoryState.archived, user.id)
            archived_count += 1
        except HTTPException as e:
            if e.status_code == 404:
                not_found_count += 1
            else:
                raise e
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error committing archival: {e}")
    
    return {"message": f"Successfully archived {archived_count} memories. Not found: {not_found_count}."}


class PauseMemoriesRequestData(BaseModel):
    memory_ids: Optional[List[UUID]] = None
    category_ids: Optional[List[UUID]] = None
    app_id: Optional[UUID] = None
    global_pause_for_user: bool = False
    state: Optional[MemoryState] = MemoryState.paused


# Pause access to memories
@router.post("/actions/pause", status_code=200)
async def pause_memories(
    request: PauseMemoriesRequestData,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)

    state_to_set = request.state or MemoryState.paused

    count = 0
    if request.global_pause_for_user:
        memories_to_update = db.query(Memory).filter(
            Memory.user_id == user.id,
        ).all()
        for memory_item in memories_to_update:
            update_memory_state(db, memory_item.id, state_to_set, user.id)
            count += 1
        message = f"Successfully set state for all {count} accessible memories for user."

    elif request.app_id:
        memories_to_update = db.query(Memory).filter(
            Memory.app_id == request.app_id,
            Memory.user_id == user.id,
        ).all()
        for memory_item in memories_to_update:
            update_memory_state(db, memory_item.id, state_to_set, user.id)
            count += 1
        message = f"Successfully set state for {count} memories for app {request.app_id}."
    
    elif request.memory_ids:
        for mem_id in request.memory_ids:
            memory_to_update = db.query(Memory).filter(Memory.id == mem_id, Memory.user_id == user.id).first()
            if memory_to_update:
                 update_memory_state(db, mem_id, state_to_set, user.id)
                 count += 1
        message = f"Successfully set state for {count} specified memories."

    elif request.category_ids:
        memories_to_update = db.query(Memory).join(Memory.categories).filter(
            Memory.user_id == user.id,
            Category.id.in_(request.category_ids),
            Memory.state != MemoryState.deleted,
        ).distinct().all()
        for memory_item in memories_to_update:
            update_memory_state(db, memory_item.id, state_to_set, user.id)
            count += 1
        message = f"Successfully set state for {count} memories in {len(request.category_ids)} categories."
    else:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid pause request parameters. Specify memories, app, categories, or global_pause_for_user.")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error committing state changes: {e}")
        
    return {"message": message}


# Get memory access logs
@router.get("/{memory_id}/access-log")
async def get_memory_access_log(
    memory_id: UUID,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)

    memory_owner_check = get_memory_or_404(db, memory_id, user.id)
    if memory_owner_check.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access logs for this memory")

    query = db.query(MemoryAccessLog).filter(MemoryAccessLog.memory_id == memory_id)
    total = query.count()
    logs = query.order_by(MemoryAccessLog.accessed_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    for log_item in logs:
        app = db.query(App).filter(App.id == log_item.app_id).first()
        log_item.app_name = app.name if app else None

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "logs": logs
    }


class UpdateMemoryRequestData(BaseModel):
    memory_content: str


# Update a memory
@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: UUID,
    request: UpdateMemoryRequestData,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    
    memory_to_update = get_memory_or_404(db, memory_id, user.id)

    if memory_to_update.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this memory")

    memory_to_update.content = request.memory_content
    try:
        db.commit()
        db.refresh(memory_to_update)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
        
    return MemoryResponse(
        id=memory_to_update.id,
        content=memory_to_update.content,
        created_at=memory_to_update.created_at,
        state=memory_to_update.state.value if memory_to_update.state else None,
        app_id=memory_to_update.app_id,
        app_name=memory_to_update.app.name if memory_to_update.app else "Unknown App",
        categories=[cat.name for cat in memory_to_update.categories],
        metadata_=memory_to_update.metadata_
    )


class FilterMemoriesRequestData(BaseModel):
    search_query: Optional[str] = None
    app_ids: Optional[List[UUID]] = None
    category_ids: Optional[List[UUID]] = None
    sort_column: Optional[str] = None
    sort_direction: Optional[str] = None
    from_date: Optional[int] = None
    to_date: Optional[int] = None
    show_archived: Optional[bool] = False


@router.post("/filter", response_model=List[MemoryResponse])
async def filter_memories(
    request: FilterMemoriesRequestData,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)

    query = db.query(Memory).filter(
        Memory.user_id == user.id,
        Memory.state != MemoryState.deleted,
    )

    if not request.show_archived:
        query = query.filter(Memory.state != MemoryState.archived)

    if request.search_query:
        query = query.filter(Memory.content.ilike(f"%{request.search_query}%"))

    if request.app_ids:
        query = query.filter(Memory.app_id.in_(request.app_ids))

    query = query.outerjoin(App, Memory.app_id == App.id)

    if request.category_ids:
        query = query.join(Memory.categories).filter(Category.id.in_(request.category_ids))
    else:
        query = query.outerjoin(Memory.categories)

    if request.from_date:
        from_datetime = datetime.fromtimestamp(request.from_date, tz=UTC)
        query = query.filter(Memory.created_at >= from_datetime)

    if request.to_date:
        to_datetime = datetime.fromtimestamp(request.to_date, tz=UTC)
        query = query.filter(Memory.created_at <= to_datetime)

    if request.sort_column and request.sort_direction:
        sort_direction = request.sort_direction.lower()
        if sort_direction not in ['asc', 'desc']:
            raise HTTPException(status_code=400, detail="Invalid sort direction")

        sort_mapping = {
            'memory': Memory.content,
            'app_name': App.name,
            'created_at': Memory.created_at,
        }
        
        if request.sort_column == 'categories':
            query = query.order_by(Memory.created_at.desc())
        elif request.sort_column in sort_mapping:
            sort_field = sort_mapping[request.sort_column]
            if sort_direction == 'desc':
                query = query.order_by(sort_field.desc())
            else:
                query = query.order_by(sort_field.asc())
        else:
            query = query.order_by(Memory.created_at.desc())
    else:
        query = query.order_by(Memory.created_at.desc())

    query = query.options(
        joinedload(Memory.categories),
        joinedload(Memory.app)
    ).distinct(Memory.id)

    # Get ALL filtered memories (no pagination)
    memories = query.all()

    return [
        MemoryResponse(
            id=mem.id,
            content=mem.content,
            created_at=mem.created_at,
            state=mem.state.value if mem.state else None,
            app_id=mem.app_id,
            app_name=mem.app.name if mem.app else "Unknown App",
            categories=[cat.name for cat in mem.categories],
            metadata_=mem.metadata_
        )
        for mem in memories
    ]


@router.get("/{memory_id}/related", response_model=List[MemoryResponse])
async def get_related_memories(
    memory_id: UUID,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    
    source_memory = get_memory_or_404(db, memory_id, user.id)
    if source_memory.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access related memories for this item.")
        
    category_ids = [category.id for category in source_memory.categories]
    
    if not category_ids:
        return []
    
    # First, get memory IDs with their category counts
    subquery = db.query(
        Memory.id,
        func.count(Category.id).label('category_count')
    ).filter(
        Memory.user_id == user.id,
        Memory.id != memory_id,
        Memory.state != MemoryState.deleted
    ).join(Memory.categories).filter(
        Category.id.in_(category_ids)
    ).group_by(Memory.id).subquery()
    
    # Then join with full memory data and order properly
    query = db.query(Memory).join(
        subquery, Memory.id == subquery.c.id
    ).options(
        joinedload(Memory.categories),
        joinedload(Memory.app)
    ).order_by(
        subquery.c.category_count.desc(),
        Memory.created_at.desc()
    )
    
    # Get ALL related memories (no pagination)
    related_memories = query.all()

    return [
        MemoryResponse(
            id=item.id,
            content=item.content,
            created_at=item.created_at,
            state=item.state.value if item.state else None,
            app_id=item.app_id,
            app_name=item.app.name if item.app else "Unknown App",
            categories=[cat.name for cat in item.categories],
            metadata_=item.metadata_
        )
        for item in related_memories
    ]


@router.post("/deep-life-query")
async def enhanced_deep_life_query(
    request: dict,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    """
    Enhanced Deep Life Query using Jean Memory V2 with ontology-guided analysis
    
    This endpoint provides comprehensive life analysis by:
    1. Using Jean Memory V2 for enhanced memory retrieval
    2. Leveraging ontology-guided entity extraction
    3. Providing richer context than standard UI queries
    """
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    
    query = request.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    try:
        # Use Jean Memory V2 for comprehensive memory retrieval
        from app.utils.memory import get_async_memory_client
        
        logger.warning(f"🧠 [DEEP LIFE QUERY] Starting Enhanced Deep Life Query for user {supabase_user_id_str}: '{query}'")
        logger.warning(f"🔄 [DEEP LIFE QUERY] Initializing Jean Memory V2 async client...")
        
        memory_client = await get_async_memory_client()
        logger.warning(f"✅ [DEEP LIFE QUERY] Jean Memory V2 client initialized successfully")
        
        # Get comprehensive memories from Jean Memory V2 with enhanced search
        enhanced_query = f"{query} life experiences goals values relationships achievements"
        logger.warning(f"🔍 [DEEP LIFE QUERY] Enhanced search query: '{enhanced_query}'")
        logger.warning(f"📊 [DEEP LIFE QUERY] Searching Jean Memory V2 with limit=50...")
        
        import time
        search_start_time = time.time()
        memory_results = await memory_client.search(
            query=enhanced_query,
            user_id=supabase_user_id_str,
            limit=50  # Get more comprehensive results
        )
        search_duration = time.time() - search_start_time
        logger.warning(f"⚡ [DEEP LIFE QUERY] Jean Memory V2 search completed in {search_duration:.2f}s")
        
        # Process memory results
        memories_text = []
        enhanced_context = []
        
        if isinstance(memory_results, dict) and 'results' in memory_results:
            memories = memory_results['results']
        elif isinstance(memory_results, list):
            memories = memory_results
        else:
            memories = []
        
        logger.warning(f"📋 [DEEP LIFE QUERY] Raw memory results type: {type(memory_results)}")
        logger.warning(f"📋 [DEEP LIFE QUERY] Found {len(memories)} memories for enhanced analysis")
        if len(memories) > 0:
            logger.warning(f"📋 [DEEP LIFE QUERY] Sample memory content: {memories[0].get('memory', memories[0].get('content', ''))[:100]}...")
        
        # Build enhanced context with Jean Memory V2 insights
        for i, mem in enumerate(memories[:30]):  # Use top 30 most relevant
            content = mem.get('memory', mem.get('content', ''))
            metadata = mem.get('metadata', {})
            
            if not content or len(content.strip()) < 5:
                continue
            
            # Add memory with context
            timestamp = mem.get('created_at', 'Unknown date')
            source = metadata.get('app_name', 'Jean Memory V2')
            
            enhanced_context.append({
                'content': content.strip(),
                'timestamp': timestamp,
                'source': source,
                'metadata': metadata
            })
            
            # Add to text for prompt
            memories_text.append(f"[{timestamp}] {content.strip()}")
        
        if not memories_text:
            return {
                "response": "I don't have enough memory context to provide a meaningful analysis. Please add more memories to enable deep life insights.",
                "analysis_type": "insufficient_data",
                "memories_analyzed": 0
            }
        
        # Create enhanced prompt for deep analysis
        memory_context = "\n".join(memories_text)
        
        enhanced_prompt = f"""You are an advanced AI life coach and analyst with access to comprehensive memory data enhanced with ontology-guided entity extraction. Your task is to provide deep, insightful analysis that goes beyond surface-level observations.

ENHANCED MEMORY CONTEXT (Ontology-Enhanced):
{memory_context}

USER'S DEEP LIFE QUESTION: "{query}"

ANALYSIS INSTRUCTIONS:
1. **Pattern Recognition**: Identify underlying themes, recurring patterns, and life trajectories
2. **Entity Analysis**: Recognize key people, places, events, and their relationships
3. **Growth Insights**: Highlight personal development, skill acquisition, and mindset evolution
4. **Value Alignment**: Assess how experiences align with stated or implied values
5. **Future Implications**: Suggest areas for growth and potential opportunities
6. **Holistic Perspective**: Connect diverse experiences into a coherent life narrative

Provide a thoughtful, multi-paragraph response that synthesizes information across memories to deliver profound insights. Be specific, empathetic, and actionable in your analysis.

MEMORY ANALYSIS COUNT: {len(memories_text)} memories analyzed
ENHANCEMENT: Ontology-guided entity extraction active"""

        # Use Gemini for analysis (same as regular Deep Life Query but with enhanced context)
        from app.utils.gemini import GeminiService
        gemini_service = GeminiService()
        
        logger.warning(f"🤖 [DEEP LIFE QUERY] Generating enhanced AI analysis with {len(memories_text)} memories")
        logger.warning(f"📝 [DEEP LIFE QUERY] Prompt length: {len(enhanced_prompt)} characters")
        
        analysis_start_time = time.time()
        analysis_result = await gemini_service.generate_response(enhanced_prompt)
        analysis_duration = time.time() - analysis_start_time
        
        logger.warning(f"✅ [DEEP LIFE QUERY] AI analysis completed in {analysis_duration:.2f}s")
        logger.warning(f"📤 [DEEP LIFE QUERY] Response length: {len(analysis_result)} characters")
        
        # Add metadata about the analysis
        analysis_metadata = {
            "memories_analyzed": len(memories_text),
            "analysis_type": "enhanced_jean_memory_v2",
            "ontology_enhanced": True,
            "entity_extraction": True,
            "timestamp": datetime.datetime.now(UTC).isoformat()
        }
        
        total_duration = time.time() - search_start_time
        logger.warning(f"🎉 [DEEP LIFE QUERY] COMPLETE - Total duration: {total_duration:.2f}s (search: {search_duration:.2f}s, analysis: {analysis_duration:.2f}s)")
        logger.warning(f"📊 [DEEP LIFE QUERY] Final stats - Memories: {len(memories_text)}, Response: {len(analysis_result)} chars")
        
        return {
            "response": analysis_result,
            "metadata": analysis_metadata,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"❌ [DEEP LIFE QUERY] Enhanced Deep Life Query failed for user {supabase_user_id_str}: {e}", exc_info=True)
        logger.error(f"❌ [DEEP LIFE QUERY] Query was: '{query}'")
        logger.error(f"❌ [DEEP LIFE QUERY] Error type: {type(e).__name__}")
        raise HTTPException(
            status_code=500, 
            detail=f"Enhanced analysis failed: {str(e)}"
        )


# Old entity extraction and layout functions removed
# These are now handled by the specialized function in Jean Memory V2
# Life graph data endpoint has been moved to appear before /{memory_id} route


# Simple fallback endpoint for life graph data (SQL memories only)
@router.get("/life-graph-data-simple")
async def get_life_graph_data_simple(
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    limit: int = Query(50, description="Maximum number of memories to analyze"),
    focus_query: Optional[str] = Query(None, description="Optional query to focus the graph on specific topics"),
    db: Session = Depends(get_db)
):
    """
    Simple life graph data endpoint using only SQL memories.
    No Jean Memory V2, Redis, or complex dependencies - just basic processing.
    """
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    
    try:
        # Get SQL memories using the same query as the main memories endpoint
        query = db.query(Memory).filter(
            Memory.user_id == user.id,
            Memory.state != MemoryState.deleted,
            Memory.state != MemoryState.archived
        )
        
        # Apply search filter if provided
        if focus_query:
            query = query.filter(Memory.content.ilike(f"%{focus_query}%"))
        
        # Add joins and limit
        query = query.outerjoin(App, Memory.app_id == App.id)
        query = query.order_by(Memory.created_at.desc()).limit(limit)
        
        # Get memories
        sql_memories = query.options(joinedload(Memory.app), joinedload(Memory.categories)).all()
        
        # Simple processing - just create memory nodes without complex entity extraction
        nodes = []
        for i, memory in enumerate(sql_memories):
            node = {
                'id': f"memory_{i}",
                'type': 'memory',
                'content': memory.content.strip(),
                'source': memory.app.name if memory.app else 'unknown',
                'timestamp': memory.created_at.isoformat(),
                'size': min(max(len(memory.content) / 100, 0.5), 2.0),
                'position': {
                    'x': (i % 10 - 5) * 3,  # Simple grid layout
                    'y': (i // 10 - 5) * 3,
                    'z': 0
                }
            }
            nodes.append(node)
        
        return {
            'nodes': nodes,
            'edges': [],  # Simple version doesn't include edges
            'clusters': [],
            'metadata': {
                'total_memories': len(sql_memories),
                'total_nodes': len(nodes),
                'total_edges': 0,
                'focus_query': focus_query,
                'generated_at': datetime.datetime.now(UTC).isoformat(),
                'simple_mode': True
            }
        }
        
    except Exception as e:
        logger.error(f"Simple Life Graph Data failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Simple life graph data generation failed: {str(e)}"
        )






