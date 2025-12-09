import asyncio
import json
import logging
import os
import time
from datetime import UTC, datetime, timedelta
from typing import Dict, List, Optional, Set
from uuid import UUID

from app.database import get_db
from app.models import (
    AccessControl,
    App,
    Category,
    Memory,
    MemoryAccessLog,
    MemoryState,
    MemoryStatusHistory,
    User,
)
from app.schemas import MemoryResponse
from app.utils.memory import get_memory_client, create_memory_async
from app.database import SessionLocal
from app.utils.permissions import check_memory_access_permissions
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate as sqlalchemy_paginate
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

router = APIRouter(prefix="/api/v1/memories", tags=["memories"])


# Temporal Entity Extraction Models and Prompts
class TimeRange(BaseModel):
    """Represents a time range with start and end timestamps."""
    start: datetime = Field(description="ISO 8601 timestamp when the event/activity starts")
    end: datetime = Field(description="ISO 8601 timestamp when the event/activity ends")
    name: Optional[str] = Field(default=None, description="Optional name/label for this time range")


class TemporalEntity(BaseModel):
    """Structured temporal and entity information extracted from a memory fact."""
    isEvent: bool = Field(description="Whether this memory describes a scheduled event or time-bound activity")
    isPerson: bool = Field(description="Whether this memory is primarily about a person or people")
    isPlace: bool = Field(description="Whether this memory is primarily about a location or place")
    isPromise: bool = Field(description="Whether this memory contains a commitment, promise, or agreement")
    isRelationship: bool = Field(description="Whether this memory describes a relationship between people")
    entities: List[str] = Field(default_factory=list, description="List of people, places, or things mentioned")
    timeRanges: List[TimeRange] = Field(default_factory=list, description="List of time ranges if this is a temporal memory")
    emoji: Optional[str] = Field(default=None, description="Single emoji that best represents this memory")


def build_temporal_extraction_prompt(current_date: datetime) -> str:
    """Build the temporal extraction prompt with the current date context."""
    return f"""You are an expert at extracting temporal and entity information from memory facts.

Your task is to analyze a memory fact and extract structured information in JSON format:
1. **Entity Types**: Determine if the memory is about events, people, places, promises, or relationships
2. **Temporal Information**: Extract and resolve any time references to actual ISO 8601 timestamps
3. **Named Entities**: List all people, places, and things mentioned
4. **Representation**: Choose a single emoji that captures the essence of the memory

You must return a valid JSON object with the following structure.

**Current Date Context:**
- Today's date: {current_date.strftime("%Y-%m-%d")}
- Current time: {current_date.strftime("%H:%M:%S")}
- Day of week: {current_date.strftime("%A")}

**Time Resolution Guidelines:**

Relative Time References:
- "tomorrow" → Add 1 day to current date
- "next week" → Add 7 days to current date
- "in X days/weeks/months" → Add X time units to current date
- "yesterday" → Subtract 1 day from current date

Time of Day:
- "4pm" or "16:00" → Use current date with that time
- "tomorrow at 4pm" → Use tomorrow's date at 16:00
- "morning" → 09:00, "afternoon" → 14:00, "evening" → 18:00, "night" → 21:00

Duration Estimation (when only start time is mentioned):
- Events like "wedding", "meeting", "party" → Default 2 hours duration
- "lunch", "dinner", "breakfast" → Default 1 hour duration
- "class", "workshop" → Default 1.5 hours duration
- "appointment", "call" → Default 30 minutes duration

**Entity Type Guidelines:**
- **isEvent**: True for scheduled activities, appointments, meetings, parties, ceremonies, classes, etc.
- **isPerson**: True when the primary focus is on a person
- **isPlace**: True when the primary focus is a location
- **isPromise**: True for commitments, promises, or agreements
- **isRelationship**: True for statements about relationships

**Example:**

Input: "I'm taking a glassblowing class today at Wimberly Glassworks with instructor Nick"
Output:
{{
    "isEvent": true,
    "isPerson": true,
    "isPlace": true,
    "isPromise": false,
    "isRelationship": false,
    "entities": ["Wimberly Glassworks", "Nick", "glassblowing"],
    "timeRanges": [
        {{
            "start": "{current_date.replace(hour=10, minute=0, second=0).isoformat()}",
            "end": "{current_date.replace(hour=11, minute=30, second=0).isoformat()}",
            "name": "Glassblowing Class"
        }}
    ],
    "emoji": "🎨"
}}

**Instructions:**
- Return structured data following the TemporalEntity schema
- Convert all temporal references to ISO 8601 format
- Be conservative: if there's no temporal information, leave timeRanges empty
- Multiple tags can be true (e.g., isEvent and isPerson both true for "meeting with John")
- Extract all meaningful entities (people, places, things) mentioned in the fact
- Choose an emoji that best represents the core meaning of the memory
"""


def get_memory_or_404(db: Session, memory_id: UUID) -> Memory:
    memory = db.query(Memory).filter(Memory.id == memory_id).first()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


def update_memory_state(db: Session, memory_id: UUID, new_state: MemoryState, user_id: UUID):
    memory = get_memory_or_404(db, memory_id)
    old_state = memory.state

    # Update memory state
    memory.state = new_state
    if new_state == MemoryState.archived:
        memory.archived_at = datetime.now(UTC)
    elif new_state == MemoryState.deleted:
        memory.deleted_at = datetime.now(UTC)

    # Record state change
    history = MemoryStatusHistory(
        memory_id=memory_id,
        changed_by=user_id,
        old_state=old_state,
        new_state=new_state
    )
    db.add(history)
    db.commit()
    return memory


async def extract_temporal_entity(memory_client, fact: str) -> Optional[Dict]:
    """
    Extract temporal and entity information from a memory fact using LLM.

    Args:
        memory_client: The mem0 memory client
        fact: The memory fact text to analyze

    Returns:
        Dictionary with temporal/entity information, or None if extraction fails
    """
    try:
        # Use the memory client's LLM to extract temporal information
        from openai import AsyncOpenAI

        # Get LLM config from memory client
        llm_config = memory_client.config.llm.config

        # Handle different config formats (dict vs object)
        if isinstance(llm_config, dict):
            api_key = llm_config.get('api_key')
            base_url = llm_config.get('openai_base_url')
            model = llm_config.get('model', 'gpt-4o-mini')
        else:
            api_key = llm_config.api_key
            base_url = llm_config.openai_base_url if hasattr(llm_config, 'openai_base_url') else None
            model = llm_config.model if hasattr(llm_config, 'model') else 'gpt-4o-mini'

        # Initialize OpenAI client
        openai_client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )

        # Build the prompt with current date context
        temporal_prompt = build_temporal_extraction_prompt(datetime.now())

        # Call LLM with temporal extraction prompt
        response = await openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": temporal_prompt},
                {"role": "user", "content": f"Extract temporal and entity information from this memory fact:\n\n{fact}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )

        content = response.choices[0].message.content
        if not content:
            logging.warning("LLM returned empty content for temporal extraction")
            return None

        # Parse and validate with Pydantic
        temporal_data = json.loads(content)

        # Convert timeRanges ISO strings to datetime objects for validation
        if "timeRanges" in temporal_data:
            for time_range in temporal_data["timeRanges"]:
                if isinstance(time_range.get("start"), str):
                    time_range["start"] = datetime.fromisoformat(time_range["start"].replace("Z", "+00:00"))
                if isinstance(time_range.get("end"), str):
                    time_range["end"] = datetime.fromisoformat(time_range["end"].replace("Z", "+00:00"))

        # Validate with Pydantic model
        temporal_entity = TemporalEntity(**temporal_data)

        # Convert back to serializable dict format
        result = {
            "isEvent": temporal_entity.isEvent,
            "isPerson": temporal_entity.isPerson,
            "isPlace": temporal_entity.isPlace,
            "isPromise": temporal_entity.isPromise,
            "isRelationship": temporal_entity.isRelationship,
            "entities": temporal_entity.entities,
            "emoji": temporal_entity.emoji
        }

        # Convert timeRanges to serializable format
        if temporal_entity.timeRanges:
            result["timeRanges"] = []
            for tr in temporal_entity.timeRanges:
                time_range_dict = {
                    "start": tr.start.isoformat() if isinstance(tr.start, datetime) else tr.start,
                    "end": tr.end.isoformat() if isinstance(tr.end, datetime) else tr.end,
                }
                if tr.name:
                    time_range_dict["name"] = tr.name
                result["timeRanges"].append(time_range_dict)
        else:
            result["timeRanges"] = []

        logging.info(f"✅ Temporal extraction: isEvent={result['isEvent']}, entities={len(result['entities'])}, timeRanges={len(result['timeRanges'])}")
        return result

    except Exception as e:
        logging.warning(f"Failed to extract temporal information: {e}")
        return None

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


# List all memories with filtering
@router.get("/", response_model=Page[MemoryResponse])
async def list_memories(
    user_id: str,
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
    params: Params = Depends(),
    search_query: Optional[str] = None,
    sort_column: Optional[str] = Query(None, description="Column to sort by (memory, categories, app_name, created_at)"),
    sort_direction: Optional[str] = Query(None, description="Sort direction (asc or desc)"),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Build base query
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
        from_datetime = datetime.fromtimestamp(from_date, tz=UTC)
        query = query.filter(Memory.created_at >= from_datetime)

    if to_date:
        to_datetime = datetime.fromtimestamp(to_date, tz=UTC)
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
        sort_field = getattr(Memory, sort_column, None)
        if sort_field:
            query = query.order_by(sort_field.desc()) if sort_direction == "desc" else query.order_by(sort_field.asc())

    # Add eager loading for app, categories, and user
    query = query.options(
        joinedload(Memory.app),
        joinedload(Memory.categories),
        joinedload(Memory.user)
    ).distinct(Memory.id)

    # Get paginated results with transformer
    return sqlalchemy_paginate(
        query,
        params,
        transformer=lambda items: [
            MemoryResponse(
                id=memory.id,
                content=memory.content,
                created_at=memory.created_at,
                state=memory.state.value,
                app_id=memory.app_id,
                app_name=memory.app.name if memory.app else None,
                categories=[category.name for category in memory.categories],
                metadata_=memory.metadata_,
                user_id=memory.user.user_id if memory.user else None,
                user_email=memory.user.email if memory.user else None
            )
            for memory in items
            if check_memory_access_permissions(db, memory, app_id)
        ]
    )


# Get all categories
@router.get("/categories")
async def get_categories(
    user_id: str,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get unique categories associated with the user's memories
    # Get all memories
    memories = db.query(Memory).filter(Memory.user_id == user.id, Memory.state != MemoryState.deleted, Memory.state != MemoryState.archived).all()
    # Get all categories from memories
    categories = [category for memory in memories for category in memory.categories]
    # Get unique categories
    unique_categories = list(set(categories))

    return {
        "categories": unique_categories,
        "total": len(unique_categories)
    }


class CreateMemoryRequest(BaseModel):
    user_id: str
    text: str
    metadata: dict = {}
    infer: bool = True
    app: str = "openmemory"
    timestamp: Optional[int] = None  # Unix timestamp in seconds


# Create new memory
@router.post("/")
async def create_memory(
    request: CreateMemoryRequest,
    db: Session = Depends(get_db)
):
    # Get or create user
    user = db.query(User).filter(User.user_id == request.user_id).first()
    if not user:
        # Extract email from metadata if provided
        user_email = None
        if request.metadata and isinstance(request.metadata, dict):
            user_email = request.metadata.get("user_email")

        user = User(user_id=request.user_id, name=request.user_id, email=user_email)
        db.add(user)
        db.commit()
        db.refresh(user)
        logging.info(f"Auto-created user: {request.user_id} with email: {user_email}")

    # Log what we're about to do
    logging.info(f"Creating memory for user_id: {request.user_id} with app: {request.app}")

    # Get or create the app - handle both UUID and name
    app_obj = None
    try:
        # Try to parse as UUID first
        app_uuid = UUID(request.app)
        app_obj = db.query(App).filter(App.id == app_uuid).first()
        if not app_obj:
            raise HTTPException(status_code=404, detail=f"App with ID {request.app} not found")
    except (ValueError, AttributeError):
        # Not a UUID, treat as app name
        app_obj = db.query(App).filter(App.name == request.app).first()
        if not app_obj:
            # Create the app if it doesn't exist
            app_obj = App(
                owner_id=user.id,
                name=request.app,
                description=f"Auto-created app for {request.app}"
            )
            db.add(app_obj)
            db.commit()
            db.refresh(app_obj)
            logging.info(f"Created new app: {request.app} with ID: {app_obj.id}")

    # Try to get memory client safely
    try:
        memory_client = await get_memory_client()
        if not memory_client:
            raise Exception("Memory client is not available")
    except Exception as client_error:
        logging.warning(f"Memory client unavailable: {client_error}. Creating memory in database only.")
        # Return a json response with the error
        return {
            "error": str(client_error)
        }


    # Prepare metadata with timestamp
    memory_metadata = request.metadata.copy() if request.metadata else {}
    if request.timestamp:
        memory_metadata['timestamp'] = request.timestamp
        memory_metadata['timestamp_iso'] = datetime.fromtimestamp(request.timestamp, tz=UTC).isoformat()

    # Add user info to metadata
    memory_metadata['user_id'] = request.user_id
    if user.email:
        memory_metadata['user_email'] = user.email

    # Create a placeholder memory record immediately
    placeholder_memory = Memory(
        user_id=user.id,
        app_id=app_obj.id,
        content=request.text,
        metadata_=memory_metadata,
        state=MemoryState.processing,  # Mark as processing
        created_at=datetime.fromtimestamp(request.timestamp, tz=UTC) if request.timestamp else None
    )
    db.add(placeholder_memory)
    db.commit()
    db.refresh(placeholder_memory)
    
    # Start memory creation in background (non-blocking)
    async def create_memory_background():
        """Background task to create memory without blocking the response"""
        # Create a new database session for the background task
        db_session = SessionLocal()
        
        try:
            start_time = time.time()

            # Prepare metadata for mem0
            mem0_metadata = {
                "source_app": "openmemory",
                "mcp_client": request.app,
            }

            # Note: mem0 doesn't support timestamp parameter in add()
            # Timestamps are stored in our database metadata instead

            qdrant_response = await memory_client.add(
                request.text,
                user_id=request.user_id,
                metadata=mem0_metadata,
                infer=request.infer
            )
        
            # Log timing information
            total_duration = time.time() - start_time
            logging.info(f"Background memory creation timing - Total: {total_duration:.3f}s")
            
            # Log the response for debugging
            logging.info(f"Background Qdrant response: {qdrant_response}")
            
            # Get fresh user and app objects from the new session
            user_obj = db_session.query(User).filter(User.user_id == request.user_id).first()
            app_obj = db_session.query(App).filter(App.name == request.app).first()
            
            # Get the placeholder memory from the new session using its ID
            placeholder_memory_bg = db_session.query(Memory).filter(Memory.id == placeholder_memory.id).first()
            if not placeholder_memory_bg:
                logging.error(f"Placeholder memory {placeholder_memory.id} not found in background session")
                return
            
            # Process Qdrant response and update database
            if isinstance(qdrant_response, dict) and 'results' in qdrant_response:
                if qdrant_response['results']:  # If there are results
                    add_count = 0
                    for idx, result in enumerate(qdrant_response['results']):
                        if result['event'] == 'ADD':
                            add_count += 1
                            # Get the Qdrant-generated ID
                            memory_id = UUID(result['id'])

                            # Extract temporal/entity information from the memory fact
                            fact_content = result['memory']
                            temporal_info = await extract_temporal_entity(memory_client, fact_content)

                            # Prepare metadata with temporal information
                            enriched_metadata = memory_metadata.copy()
                            if temporal_info:
                                enriched_metadata.update({
                                    "isEvent": temporal_info.get("isEvent", False),
                                    "isPerson": temporal_info.get("isPerson", False),
                                    "isPlace": temporal_info.get("isPlace", False),
                                    "isPromise": temporal_info.get("isPromise", False),
                                    "isRelationship": temporal_info.get("isRelationship", False),
                                    "entities": temporal_info.get("entities", []),
                                    "timeRanges": temporal_info.get("timeRanges", []),
                                    "emoji": temporal_info.get("emoji")
                                })

                                # Create a display name with emoji if available
                                if temporal_info.get("emoji"):
                                    fact_preview = fact_content[:50] + ("..." if len(fact_content) > 50 else "")
                                    enriched_metadata["display_name"] = f"{temporal_info['emoji']} {fact_preview}"

                            if add_count == 1:
                                # Update placeholder memory with the first ADD result
                                placeholder_memory_bg.id = memory_id
                                placeholder_memory_bg.content = fact_content
                                placeholder_memory_bg.state = MemoryState.active
                                placeholder_memory_bg.metadata_ = enriched_metadata
                                memory_obj = placeholder_memory_bg
                            else:
                                # Create NEW memory records for additional facts
                                memory_obj = Memory(
                                    id=memory_id,
                                    user_id=user_obj.id,
                                    app_id=app_obj.id,
                                    content=fact_content,
                                    metadata_=enriched_metadata,
                                    state=MemoryState.active
                                )
                                db_session.add(memory_obj)

                            # Create history entry
                            history = MemoryStatusHistory(
                                memory_id=memory_id,
                                changed_by=user_obj.id,
                                old_state=MemoryState.processing,
                                new_state=MemoryState.active
                            )
                            db_session.add(history)

                            db_session.commit()
                            db_session.refresh(memory_obj)

                            # Log creation with temporal info
                            temporal_str = ""
                            if temporal_info:
                                temporal_str = f" [emoji={temporal_info.get('emoji')}, isEvent={temporal_info.get('isEvent')}, entities={len(temporal_info.get('entities', []))}]"
                            logging.info(f"Background memory created/updated: {memory_id}{temporal_str}")

                    # If no ADD events occurred (all were NONE/UPDATE), mark placeholder as deleted
                    if add_count == 0:
                        placeholder_memory_bg.state = MemoryState.deleted

                        # Create history entry
                        history = MemoryStatusHistory(
                            memory_id=placeholder_memory_bg.id,
                            changed_by=user_obj.id,
                            old_state=MemoryState.processing,
                            new_state=MemoryState.deleted
                        )
                        db_session.add(history)

                        db_session.commit()
                        db_session.refresh(placeholder_memory_bg)
                        logging.info(f"Background memory completed (all facts were duplicates/updates): {placeholder_memory_bg.id}")
                else:  # No results - no meaningful facts extracted
                    # Keep the original content but mark as deleted
                    placeholder_memory_bg.state = MemoryState.deleted

                    # Create history entry
                    history = MemoryStatusHistory(
                        memory_id=placeholder_memory_bg.id,
                        changed_by=user_obj.id,
                        old_state=MemoryState.processing,
                        new_state=MemoryState.deleted
                    )
                    db_session.add(history)

                    db_session.commit()
                    db_session.refresh(placeholder_memory_bg)
                    logging.info(f"Background memory completed (no facts extracted): {placeholder_memory_bg.id}")
                        
        except Exception as e:
            logging.warning(f"Background memory creation failed: {e}")
            # Update placeholder to show error state
            try:
                # Get the placeholder memory from the session for error handling
                placeholder_memory_bg = db_session.query(Memory).filter(Memory.id == placeholder_memory.id).first()
                if placeholder_memory_bg:
                    placeholder_memory_bg.state = MemoryState.deleted
                    placeholder_memory_bg.content = f"Error: {str(e)}"
                    db_session.commit()
                    logging.error(f"Background memory creation failed, marked as deleted: {placeholder_memory_bg.id}")
                else:
                    logging.error(f"Could not find placeholder memory {placeholder_memory.id} for error handling")
            except Exception as fallback_error:
                logging.error(f"Failed to update placeholder memory: {fallback_error}")
        finally:
            db_session.close()
    
    # Fire off the background task
    asyncio.create_task(create_memory_background())
    
    logging.info(f"Memory creation started in background, returning immediately with ID: {placeholder_memory.id}")
    return placeholder_memory





# Get memory by ID
@router.get("/{memory_id}")
async def get_memory(
    memory_id: UUID,
    db: Session = Depends(get_db)
):
    memory = get_memory_or_404(db, memory_id)
    return {
        "id": memory.id,
        "text": memory.content,
        "created_at": int(memory.created_at.timestamp()),
        "state": memory.state.value,
        "app_id": memory.app_id,
        "app_name": memory.app.name if memory.app else None,
        "categories": [category.name for category in memory.categories],
        "metadata_": memory.metadata_
    }


class DeleteMemoriesRequest(BaseModel):
    memory_ids: List[UUID]
    user_id: str

# Delete multiple memories
@router.delete("/")
async def delete_memories(
    request: DeleteMemoriesRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get memory client to delete from vector store
    try:
        memory_client = await get_memory_client()
        if not memory_client:
            raise HTTPException(
                status_code=503,
                detail="Memory client is not available"
            )
    except HTTPException:
        raise
    except Exception as client_error:
        logging.error(f"Memory client initialization failed: {client_error}")
        raise HTTPException(
            status_code=503,
            detail=f"Memory service unavailable: {str(client_error)}"
        )

    # Delete from vector store then mark as deleted in database
    for memory_id in request.memory_ids:
        try:
            await memory_client.delete(str(memory_id))
        except Exception as delete_error:
            logging.warning(f"Failed to delete memory {memory_id} from vector store: {delete_error}")

        update_memory_state(db, memory_id, MemoryState.deleted, user.id)

    return {"message": f"Successfully deleted {len(request.memory_ids)} memories"}


# Archive memories
@router.post("/actions/archive")
async def archive_memories(
    memory_ids: List[UUID],
    user_id: UUID,
    db: Session = Depends(get_db)
):
    for memory_id in memory_ids:
        update_memory_state(db, memory_id, MemoryState.archived, user_id)
    return {"message": f"Successfully archived {len(memory_ids)} memories"}


class PauseMemoriesRequest(BaseModel):
    memory_ids: Optional[List[UUID]] = None
    category_ids: Optional[List[UUID]] = None
    app_id: Optional[UUID] = None
    all_for_app: bool = False
    global_pause: bool = False
    state: Optional[MemoryState] = None
    user_id: str

# Pause access to memories
@router.post("/actions/pause")
async def pause_memories(
    request: PauseMemoriesRequest,
    db: Session = Depends(get_db)
):
    
    global_pause = request.global_pause
    all_for_app = request.all_for_app
    app_id = request.app_id
    memory_ids = request.memory_ids
    category_ids = request.category_ids
    state = request.state or MemoryState.paused

    user = db.query(User).filter(User.user_id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_id = user.id
    
    if global_pause:
        # Pause all memories
        memories = db.query(Memory).filter(
            Memory.state != MemoryState.deleted,
            Memory.state != MemoryState.archived
        ).all()
        for memory in memories:
            update_memory_state(db, memory.id, state, user_id)
        return {"message": "Successfully paused all memories"}

    if app_id:
        # Pause all memories for an app
        memories = db.query(Memory).filter(
            Memory.app_id == app_id,
            Memory.user_id == user.id,
            Memory.state != MemoryState.deleted,
            Memory.state != MemoryState.archived
        ).all()
        for memory in memories:
            update_memory_state(db, memory.id, state, user_id)
        return {"message": f"Successfully paused all memories for app {app_id}"}
    
    if all_for_app and memory_ids:
        # Pause all memories for an app
        memories = db.query(Memory).filter(
            Memory.user_id == user.id,
            Memory.state != MemoryState.deleted,
            Memory.id.in_(memory_ids)
        ).all()
        for memory in memories:
            update_memory_state(db, memory.id, state, user_id)
        return {"message": "Successfully paused all memories"}

    if memory_ids:
        # Pause specific memories
        for memory_id in memory_ids:
            update_memory_state(db, memory_id, state, user_id)
        return {"message": f"Successfully paused {len(memory_ids)} memories"}

    if category_ids:
        # Pause memories by category
        memories = db.query(Memory).join(Memory.categories).filter(
            Category.id.in_(category_ids),
            Memory.state != MemoryState.deleted,
            Memory.state != MemoryState.archived
        ).all()
        for memory in memories:
            update_memory_state(db, memory.id, state, user_id)
        return {"message": f"Successfully paused memories in {len(category_ids)} categories"}

    raise HTTPException(status_code=400, detail="Invalid pause request parameters")


# Get memory access logs
@router.get("/{memory_id}/access-log")
async def get_memory_access_log(
    memory_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(MemoryAccessLog).filter(MemoryAccessLog.memory_id == memory_id)
    total = query.count()
    logs = query.order_by(MemoryAccessLog.accessed_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # Get app name
    for log in logs:
        app = db.query(App).filter(App.id == log.app_id).first()
        log.app_name = app.name if app else None

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "logs": logs
    }


class UpdateMemoryRequest(BaseModel):
    memory_content: str
    user_id: str
    target_app_id: Optional[UUID] = None

# Update a memory
@router.put("/{memory_id}")
async def update_memory(
    memory_id: UUID,
    request: UpdateMemoryRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    memory = get_memory_or_404(db, memory_id)
    memory.content = request.memory_content
    if request.target_app_id:
        memory.app_id = request.target_app_id
    db.commit()
    db.refresh(memory)
    return memory

class MoveMemoriesRequest(BaseModel):
    target_app_id: UUID  # Changed to str to handle UUID strings from frontend
    user_id: str

@router.post("/{app_id}/memories/move/")
async def move_memories_to_app(
    app_id: UUID,
    request: UpdateMemoryRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")    
    # Get memories to move
    memories = db.query(Memory).filter(
        Memory.id.in_(request.memory_ids),
        Memory.app_id == app_id,
        # Memory.user_id == user.id,
        # Memory.state != MemoryState.deleted
    ).all()
    
    if not memories:
        raise HTTPException(status_code=404, detail="No memories found to move")
    
    # Move memories to target app
    moved_count = 0
    for memory in memories:
        try:
            await update_memory(memory.id, request, db)
            moved_count += 1
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to move memory {memory.id}: {str(e)}")
    
    return {
        "status": "success",
        "message": f"Successfully moved {moved_count} memories to {request.target_app_id}",
        "moved_count": moved_count
    }



class FilterMemoriesRequest(BaseModel):
    user_id: str
    page: int = 1
    size: int = 10
    search_query: Optional[str] = None
    app_ids: Optional[List[UUID]] = None
    category_ids: Optional[List[UUID]] = None
    sort_column: Optional[str] = None
    sort_direction: Optional[str] = None
    from_date: Optional[int] = None
    to_date: Optional[int] = None
    show_archived: Optional[bool] = False

@router.post("/filter", response_model=Page[MemoryResponse])
async def filter_memories(
    request: FilterMemoriesRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Build base query
    # Superusers can see all memories, regular users only see their own
    if user.is_superuser:
        query = db.query(Memory).filter(
            Memory.state != MemoryState.deleted,
        )
    else:
        query = db.query(Memory).filter(
            Memory.user_id == user.id,
            Memory.state != MemoryState.deleted,
        )

    # Filter archived memories based on show_archived parameter
    if not request.show_archived:
        query = query.filter(Memory.state != MemoryState.archived)

    # Apply search filter
    if request.search_query:
        query = query.filter(Memory.content.ilike(f"%{request.search_query}%"))

    # Apply app filter
    if request.app_ids:
        query = query.filter(Memory.app_id.in_(request.app_ids))

    # Add joins for app and categories
    query = query.outerjoin(App, Memory.app_id == App.id)

    # Apply category filter
    if request.category_ids:
        query = query.join(Memory.categories).filter(Category.id.in_(request.category_ids))
    else:
        query = query.outerjoin(Memory.categories)

    # Apply date filters
    if request.from_date:
        from_datetime = datetime.fromtimestamp(request.from_date, tz=UTC)
        query = query.filter(Memory.created_at >= from_datetime)

    if request.to_date:
        to_datetime = datetime.fromtimestamp(request.to_date, tz=UTC)
        query = query.filter(Memory.created_at <= to_datetime)

    # Apply sorting
    if request.sort_column and request.sort_direction:
        sort_direction = request.sort_direction.lower()
        if sort_direction not in ['asc', 'desc']:
            raise HTTPException(status_code=400, detail="Invalid sort direction")

        sort_mapping = {
            'memory': Memory.content,
            'app_name': App.name,
            'created_at': Memory.created_at
        }

        if request.sort_column not in sort_mapping:
            raise HTTPException(status_code=400, detail="Invalid sort column")

        sort_field = sort_mapping[request.sort_column]
        if sort_direction == 'desc':
            query = query.order_by(sort_field.desc())
        else:
            query = query.order_by(sort_field.asc())
    else:
        # Default sorting
        query = query.order_by(Memory.created_at.desc())

    # Add eager loading for categories and make the query distinct
    query = query.options(
        joinedload(Memory.categories)
    ).distinct(Memory.id)

    # Use fastapi-pagination's paginate function
    return sqlalchemy_paginate(
        query,
        Params(page=request.page, size=request.size),
        transformer=lambda items: [
            MemoryResponse(
                id=memory.id,
                content=memory.content,
                created_at=memory.created_at,
                state=memory.state.value,
                app_id=memory.app_id,
                app_name=memory.app.name if memory.app else None,
                categories=[category.name for category in memory.categories],
                metadata_=memory.metadata_
            )
            for memory in items
        ]
    )


@router.post("/actions/recover-stuck")
async def recover_stuck_memories(
    db: Session = Depends(get_db)
):
    """Manual endpoint to check for and recover stuck processing memories"""
    stuck_memories = db.query(Memory).filter(Memory.state == MemoryState.processing).all()
    
    if not stuck_memories:
        return {"message": "No stuck processing memories found", "count": 0}
    
    return {
        "message": f"Found {len(stuck_memories)} stuck processing memories",
        "count": len(stuck_memories),
        "memories": [
            {
                "id": str(memory.id),
                "content": memory.content[:100] + "..." if len(memory.content) > 100 else memory.content,
                "created_at": memory.created_at.isoformat(),
                "user_id": memory.user_id,
                "app_id": memory.app_id
            }
            for memory in stuck_memories
        ]
    }


@router.get("/{memory_id}/related", response_model=Page[MemoryResponse])
async def get_related_memories(
    memory_id: UUID,
    user_id: str,
    params: Params = Depends(),
    db: Session = Depends(get_db)
):
    # Validate user
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get the source memory
    memory = get_memory_or_404(db, memory_id)
    
    # Extract category IDs from the source memory
    category_ids = [category.id for category in memory.categories]
    
    if not category_ids:
        return Page.create([], total=0, params=params)
    
    # Build query for related memories
    query = db.query(Memory).distinct(Memory.id).filter(
        Memory.user_id == user.id,
        Memory.id != memory_id,
        Memory.state != MemoryState.deleted
    ).join(Memory.categories).filter(
        Category.id.in_(category_ids)
    ).options(
        joinedload(Memory.categories),
        joinedload(Memory.app)
    ).order_by(
        func.count(Category.id).desc(),
        Memory.created_at.desc()
    ).group_by(Memory.id)
    
    # ⚡ Force page size to be 5
    params = Params(page=params.page, size=5)
    
    return sqlalchemy_paginate(
        query,
        params,
        transformer=lambda items: [
            MemoryResponse(
                id=memory.id,
                content=memory.content,
                created_at=memory.created_at,
                state=memory.state.value,
                app_id=memory.app_id,
                app_name=memory.app.name if memory.app else None,
                categories=[category.name for category in memory.categories],
                metadata_=memory.metadata_
            )
            for memory in items
        ]
    )

    