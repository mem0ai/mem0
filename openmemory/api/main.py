import asyncio
import datetime
import logging
from contextlib import asynccontextmanager
from uuid import uuid4

# Configure logging at INFO level
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from app.config import DEFAULT_APP_ID, USER_ID
from app.database import Base, SessionLocal, engine
from app.mcp_server import setup_mcp_server
from app.models import App, Memory, MemoryState, MemoryStatusHistory, User
from app.utils.memory import get_memory_client
from app.routers import apps_router, backup_router, config_router, graph_router, memories_router, prompts_router, stats_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination


# We'll use FastAPI's lifespan events instead of running at module import
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("=== STARTUP: Starting recovery of stuck processing memories ===")
    try:
        await recover_stuck_processing_memories()
        print("=== STARTUP: Recovery completed ===")
    except Exception as e:
        print(f"=== STARTUP RECOVERY ERROR: {e} ===")
        logging.error(f"Startup recovery failed: {e}")
    
    yield
    
    # Shutdown (nothing to do here for now)
    pass


app = FastAPI(name="OpenMemory API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create all tables
Base.metadata.create_all(bind=engine)

# Check for USER_ID and create default user if needed
def create_default_user():
    db = SessionLocal()
    try:
        # Check if user exists
        user = db.query(User).filter(User.user_id == USER_ID).first()
        if not user:
            # Create default user
            user = User(
                id=uuid4(),
                user_id=USER_ID,
                name="Default User",
                created_at=datetime.datetime.now(datetime.UTC)
            )
            db.add(user)
            db.commit()
    finally:
        db.close()


def create_default_app():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == USER_ID).first()
        if not user:
            return

        # Check if app already exists
        existing_app = db.query(App).filter(
            App.name == DEFAULT_APP_ID,
            App.owner_id == user.id
        ).first()

        if existing_app:
            return

        app = App(
            id=uuid4(),
            name=DEFAULT_APP_ID,
            owner_id=user.id,
            created_at=datetime.datetime.now(datetime.UTC),
            updated_at=datetime.datetime.now(datetime.UTC),
        )
        db.add(app)
        db.commit()
    finally:
        db.close()


async def recover_stuck_processing_memories():
    """
    Recovery mechanism for memories stuck in processing state.
    This happens when the server crashes or restarts while background tasks are running.
    """
    db = SessionLocal()
    try:
        # Find all memories stuck in processing state
        stuck_memories = db.query(Memory).filter(
            Memory.state == MemoryState.processing
        ).all()
        
        if not stuck_memories:
            print("=== RECOVERY: No stuck processing memories found ===")
            logging.info("No stuck processing memories found")
            return
            
        print(f"=== RECOVERY: Found {len(stuck_memories)} stuck processing memories, attempting recovery ===")
        logging.info(f"Found {len(stuck_memories)} stuck processing memories, attempting recovery...")
        
        # Get memory client for processing
        try:
            memory_client = await get_memory_client()
            if not memory_client:
                raise Exception("Memory client not available")
        except Exception as e:
            logging.error(f"Memory client unavailable during recovery: {e}")
            # Mark stuck memories as deleted if we can't process them
            for memory in stuck_memories:
                memory.state = MemoryState.deleted
                memory.content = f"Recovery failed: {str(e)}"
                
                history = MemoryStatusHistory(
                    memory_id=memory.id,
                    changed_by=memory.user_id,
                    old_state=MemoryState.processing,
                    new_state=MemoryState.deleted
                )
                db.add(history)
            
            db.commit()
            logging.info(f"Marked {len(stuck_memories)} memories as deleted due to recovery failure")
            return
        
        # Process each stuck memory
        recovered_count = 0
        failed_count = 0
        
        for memory in stuck_memories:
            try:
                logging.info(f"Recovering memory {memory.id}: {memory.content[:50]}...")
                
                # Get the app for metadata
                app = db.query(App).filter(App.id == memory.app_id).first()
                user = db.query(User).filter(User.id == memory.user_id).first()
                
                if not app or not user:
                    raise Exception("Associated app or user not found")
                
                # Retry the mem0 operation
                qdrant_response = await memory_client.add(
                    memory.content,
                    user_id=user.user_id,
                    metadata={
                        "source_app": "openmemory",
                        "mcp_client": app.name,
                    }
                )
                
                # Process response similar to the original create_memory logic
                if isinstance(qdrant_response, dict) and 'results' in qdrant_response:
                    if qdrant_response['results']:  # If there are results
                        for result in qdrant_response['results']:
                            if result['event'] == 'ADD':
                                from uuid import UUID
                                # Get the new mem0-generated ID
                                new_memory_id = UUID(result['id'])
                                
                                # Update the memory with actual content and ID
                                memory.id = new_memory_id
                                memory.content = result['memory']
                                memory.state = MemoryState.active
                                
                                # Create history entry
                                history = MemoryStatusHistory(
                                    memory_id=new_memory_id,
                                    changed_by=memory.user_id,
                                    old_state=MemoryState.processing,
                                    new_state=MemoryState.active
                                )
                                db.add(history)
                                
                                recovered_count += 1
                                logging.info(f"Successfully recovered memory {new_memory_id}")
                                break
                    else:  # No results - no meaningful facts extracted
                        memory.state = MemoryState.deleted
                        
                        history = MemoryStatusHistory(
                            memory_id=memory.id,
                            changed_by=memory.user_id,
                            old_state=MemoryState.processing,
                            new_state=MemoryState.deleted
                        )
                        db.add(history)
                        
                        failed_count += 1
                        logging.info(f"Memory {memory.id} had no extractable facts, marked as deleted")
                        
            except Exception as e:
                logging.error(f"Failed to recover memory {memory.id}: {e}")
                # Mark as deleted with error info
                memory.state = MemoryState.deleted
                memory.content = f"Recovery error: {str(e)}"
                
                history = MemoryStatusHistory(
                    memory_id=memory.id,
                    changed_by=memory.user_id,
                    old_state=MemoryState.processing,
                    new_state=MemoryState.deleted
                )
                db.add(history)
                
                failed_count += 1
        
        # Commit all changes
        db.commit()
        logging.info(f"Recovery complete: {recovered_count} recovered, {failed_count} failed")
        
    except Exception as e:
        logging.error(f"Recovery process failed: {e}")
    finally:
        db.close()


# Create default user on startup (this runs during import, which is fine)
create_default_user()
create_default_app()

# Setup MCP server
setup_mcp_server(app)

# Include routers
app.include_router(memories_router)
app.include_router(apps_router)
app.include_router(stats_router)
app.include_router(config_router)
app.include_router(prompts_router)
app.include_router(backup_router)
app.include_router(graph_router)

# Add pagination support
add_pagination(app)
