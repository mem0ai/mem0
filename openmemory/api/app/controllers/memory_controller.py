"""Memory controller with method-based design.

Each complex operation is broken into small, readable methods.
Routes call these methods in sequence to show clear flow.
"""

import asyncio
import logging
from typing import Tuple
from uuid import UUID
from datetime import datetime, UTC

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import User, App, Memory, MemoryState
from app.models.schemas import CreateMemoryRequest
from app.utils.memory import get_memory_client
from app.database import SessionLocal

logger = logging.getLogger(__name__)


async def get_or_create_user_and_app(
    request: CreateMemoryRequest,
    db: Session
) -> Tuple[User, App]:
    """Get or create user and app from request.

    Args:
        request: Create memory request
        db: Database session

    Returns:
        Tuple of (User, App)

    Raises:
        HTTPException: If app ID not found
    """
    # Get or create user
    user = db.query(User).filter(User.user_id == request.user_id).first()
    if not user:
        user_email = request.metadata.get("user_email") if request.metadata else None
        user = User(user_id=request.user_id, name=request.user_id, email=user_email)
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Auto-created user: {request.user_id}")

    # Get or create app (handle both UUID and name)
    try:
        app_uuid = UUID(request.app)
        app_obj = db.query(App).filter(App.id == app_uuid).first()
        if not app_obj:
            raise HTTPException(status_code=404, detail=f"App with ID {request.app} not found")
    except (ValueError, AttributeError):
        app_obj = db.query(App).filter(App.name == request.app).first()
        if not app_obj:
            app_obj = App(
                owner_id=user.id,
                name=request.app,
                description=f"Auto-created app for {request.app}"
            )
            db.add(app_obj)
            db.commit()
            db.refresh(app_obj)
            logger.info(f"Created new app: {request.app}")

    return user, app_obj


def validate_app_active(app: App) -> None:
    """Check if app is active.

    Args:
        app: App to validate

    Raises:
        HTTPException: If app is paused
    """
    if not app.is_active:
        raise HTTPException(
            status_code=403,
            detail=f"App {app.name} is currently paused. Cannot create new memories."
        )


async def ensure_memory_client():
    """Get memory client or raise error.

    Returns:
        Initialized memory client

    Raises:
        HTTPException: If memory client unavailable
    """
    try:
        memory_client = await get_memory_client()
        if not memory_client:
            raise Exception("Memory client is not available")
        return memory_client
    except Exception as e:
        logger.warning(f"Memory client unavailable: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Memory service unavailable: {str(e)}"
        )


def add_timestamp_and_user_to_metadata(request: CreateMemoryRequest, user: User) -> dict:
    """Add timestamp and user information to metadata.

    Args:
        request: Create memory request with optional timestamp
        user: User object

    Returns:
        Metadata dict with timestamp (if provided) and user info
    """
    metadata = request.metadata.copy() if request.metadata else {}

    # Add timestamp if provided
    if request.timestamp:
        metadata['timestamp'] = request.timestamp
        metadata['timestamp_iso'] = datetime.fromtimestamp(request.timestamp, tz=UTC).isoformat()

    # Add user info
    metadata['user_id'] = request.user_id
    if user.email:
        metadata['user_email'] = user.email

    return metadata


def create_placeholder(
    user: User,
    app: App,
    request: CreateMemoryRequest,
    metadata: dict,
    db: Session
) -> Memory:
    """Create placeholder memory that shows 'processing' state.

    Args:
        user: User object
        app: App object
        request: Create memory request
        metadata: Prepared metadata
        db: Database session

    Returns:
        Placeholder Memory object in processing state
    """
    placeholder = Memory(
        user_id=user.id,
        app_id=app.id,
        content=request.text,
        metadata_=metadata,
        state=MemoryState.processing,
        created_at=datetime.fromtimestamp(request.timestamp, tz=UTC) if request.timestamp else None
    )
    db.add(placeholder)
    db.commit()
    db.refresh(placeholder)
    return placeholder


async def process_memory_with_mem0(
    placeholder: Memory,
    request: CreateMemoryRequest,
    metadata: dict
) -> None:
    """Process memory with mem0 in background.

    Controller handles mem0 client lifecycle internally.

    Args:
        placeholder: Placeholder memory object
        request: Create memory request
        metadata: Memory metadata
    """
    # Get mem0 client (controller manages this, not the route)
    try:
        memory_client = await get_memory_client()
        if not memory_client:
            raise Exception("Memory client is not available")
    except Exception as e:
        logger.error(f"Memory client unavailable: {e}")
        raise HTTPException(status_code=503, detail=f"Memory service unavailable: {str(e)}")

    # Start background processing
    from app.services.temporal_service import (
        enrich_metadata_with_temporal_data,
        enrich_metadata_with_mycelia_fields,
        format_temporal_log_string
    )
    from app.services.memory_service import create_history_entry

    async def process_memory_background():
        """Background task that processes memory events from mem0."""
        import time
        import os
        db_session = SessionLocal()

        try:
            start_time = time.time()

            # Call mem0 to add memory
            qdrant_response = await memory_client.add(
                request.text,
                user_id=request.user_id,
                metadata={"source_app": "openmemory", "mcp_client": request.app},
                infer=request.infer
            )

            logger.info(f"mem0 processing time: {time.time() - start_time:.3f}s")
            logger.info(f"mem0 response: {qdrant_response}")

            # Re-fetch from background session (need fresh session objects)
            user_obj = db_session.query(User).filter(User.user_id == request.user_id).first()
            app_obj = db_session.query(App).filter(App.name == request.app).first()
            placeholder_bg = db_session.query(Memory).filter(Memory.id == placeholder.id).first()

            # TODO: Pass user/app as parameters to avoid this re-fetch

            if not placeholder_bg:
                logger.error(f"Placeholder {placeholder.id} not found")
                return

            # Process events from mem0
            if isinstance(qdrant_response, dict) and 'results' in qdrant_response:
                await process_memory_events(
                    qdrant_response['results'],
                    placeholder_bg,
                    user_obj,
                    app_obj,
                    metadata,
                    memory_client,
                    db_session
                )

        except Exception as e:
            logger.error(f"Background processing failed: {e}")
            handle_processing_error(placeholder.id, db_session, e)
        finally:
            db_session.close()

    # Fire off the background task
    asyncio.create_task(process_memory_background())
    logger.info(f"Background processing started for memory {placeholder.id}")


async def process_memory_events(
    results: list,
    placeholder: Memory,
    user: User,
    app: App,
    metadata: dict,
    memory_client,
    db: Session
) -> None:
    """Process ADD/UPDATE/DELETE/NONE events from mem0.

    Args:
        results: List of event results from mem0
        placeholder: Placeholder memory
        user: User object
        app: App object
        metadata: Memory metadata
        memory_client: mem0 client
        db: Database session
    """
    from app.services.temporal_service import format_temporal_log_string
    from app.services.memory_service import create_history_entry

    if not results:
        placeholder.state = MemoryState.deleted
        create_history_entry(db, placeholder.id, user.id, MemoryState.processing, MemoryState.deleted)
        db.commit()
        logger.info(f"No facts extracted, placeholder deleted: {placeholder.id}")
        return

    add_count = update_count = delete_count = 0
    processed_placeholder = False

    for result in results:
        event_type = result.get('event', 'NONE')

        if event_type == 'ADD':
            add_count += 1
            await handle_add_event(result, placeholder, user, app, metadata, memory_client, db, add_count == 1 and not processed_placeholder)
            if add_count == 1:
                processed_placeholder = True

        elif event_type == 'UPDATE':
            update_count += 1
            await handle_update_event(result, user, metadata, memory_client, db)

        elif event_type == 'DELETE':
            delete_count += 1
            await handle_delete_event(result, user, db)

        elif event_type == 'NONE':
            logger.info(f"Duplicate memory (NONE event): {result.get('id')}")

        else:
            logger.warning(f"Unknown event type: {event_type}")

    # Cleanup placeholder if not used
    if not processed_placeholder:
        placeholder.state = MemoryState.deleted
        create_history_entry(db, placeholder.id, user.id, MemoryState.processing, MemoryState.deleted)
        db.commit()
        logger.info(f"Placeholder deleted ({update_count} UPDATE, {delete_count} DELETE, {add_count} ADD)")


async def handle_add_event(
    result: dict,
    placeholder: Memory,
    user: User,
    app: App,
    metadata: dict,
    memory_client,
    db: Session,
    use_placeholder: bool
) -> None:
    """Handle ADD event from mem0."""
    import os
    from app.services.temporal_service import format_temporal_log_string
    from app.services.memory_service import create_history_entry

    memory_id = UUID(result['id'])
    fact_content = result['memory']

    # Extract temporal data based on mode
    import os
    mycelia_mode = os.getenv('MYCELIA_MODE', 'false').lower() == 'true'

    if mycelia_mode:
        # Full Mycelia fields: isEvent, isPerson, emoji, etc.
        from app.services.temporal_service import enrich_metadata_with_mycelia_fields
        enriched_metadata, temporal_info = await enrich_metadata_with_mycelia_fields(
            memory_client, fact_content, metadata
        )
    else:
        # Just timeRanges and entities (no entity type classifications)
        from app.services.temporal_service import enrich_metadata_with_temporal_data
        enriched_metadata, temporal_info = await enrich_metadata_with_temporal_data(
            memory_client, fact_content, metadata
        )

    if use_placeholder:
        # Reuse placeholder
        placeholder.id = memory_id
        placeholder.content = fact_content
        placeholder.state = MemoryState.active
        placeholder.metadata_ = enriched_metadata
        memory_obj = placeholder
    else:
        # Create new memory
        memory_obj = Memory(
            id=memory_id,
            user_id=user.id,
            app_id=app.id,
            content=fact_content,
            metadata_=enriched_metadata,
            state=MemoryState.active
        )
        db.add(memory_obj)

    create_history_entry(db, memory_id, user.id, MemoryState.processing, MemoryState.active)
    db.commit()
    db.refresh(memory_obj)
    logger.info(f"Memory created: {memory_id}{format_temporal_log_string(temporal_info)}")


async def handle_update_event(
    result: dict,
    user: User,
    metadata: dict,
    memory_client,
    db: Session
) -> None:
    """Handle UPDATE event from mem0."""
    import os
    from app.services.temporal_service import format_temporal_log_string
    from app.services.memory_service import create_history_entry

    memory_id = UUID(result['id'])
    existing = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user.id).first()

    if existing:
        old_content = existing.content
        old_state = existing.state
        fact_content = result['memory']

        import os
        mycelia_mode = os.getenv('MYCELIA_MODE', 'false').lower() == 'true'
        base_metadata = existing.metadata_.copy() if existing.metadata_ else {}

        if mycelia_mode:
            from app.services.temporal_service import enrich_metadata_with_mycelia_fields
            enriched_metadata, temporal_info = await enrich_metadata_with_mycelia_fields(
                memory_client, fact_content, base_metadata
            )
        else:
            from app.services.temporal_service import enrich_metadata_with_temporal_data
            enriched_metadata, temporal_info = await enrich_metadata_with_temporal_data(
                memory_client, fact_content, base_metadata
            )

        existing.content = fact_content
        existing.metadata_ = enriched_metadata
        existing.state = MemoryState.active
        existing.updated_at = datetime.now(UTC)

        create_history_entry(db, memory_id, user.id, old_state, MemoryState.active)
        db.commit()

        logger.info(f"Memory updated: {memory_id}{format_temporal_log_string(temporal_info)}")
        logger.info(f"  Old: {old_content[:100]}...")
        logger.info(f"  New: {fact_content[:100]}...")
    else:
        logger.warning(f"UPDATE event for non-existent memory {memory_id}")


async def handle_delete_event(result: dict, user: User, db: Session) -> None:
    """Handle DELETE event from mem0."""
    from app.services.memory_service import create_history_entry

    memory_id = UUID(result['id'])
    memory = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user.id).first()

    if memory:
        old_state = memory.state
        memory.state = MemoryState.deleted
        memory.deleted_at = datetime.now(UTC)

        create_history_entry(db, memory_id, user.id, old_state, MemoryState.deleted)
        db.commit()

        logger.info(f"Memory deleted (contradiction): {memory_id}")
    else:
        logger.warning(f"DELETE event for non-existent memory {memory_id}")


def handle_processing_error(placeholder_id: UUID, db: Session, error: Exception) -> None:
    """Handle errors in background processing."""
    try:
        placeholder = db.query(Memory).filter(Memory.id == placeholder_id).first()
        if placeholder:
            placeholder.state = MemoryState.deleted
            placeholder.content = f"Error: {str(error)}"
            db.commit()
            logger.error(f"Processing failed, placeholder deleted: {placeholder_id}")
    except Exception as e:
        logger.error(f"Error handling failed: {e}")
