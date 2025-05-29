"""
Background task management system for handling long-running operations.
"""
import asyncio
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Any, Callable
from pydantic import BaseModel
import logging
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Persistent storage for tasks
TASK_STORAGE_DIR = Path("/tmp/openmemory_tasks")
TASK_STORAGE_DIR.mkdir(exist_ok=True)

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"

class BackgroundTask(BaseModel):
    task_id: str
    task_type: str
    user_id: str
    status: TaskStatus
    progress: int = 0
    progress_message: str = "Starting..."
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict] = None
    error: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

# Persistent task storage
def save_task(task: BackgroundTask):
    """Save task to persistent storage"""
    try:
        task_file = TASK_STORAGE_DIR / f"{task.task_id}.json"
        with open(task_file, 'w') as f:
            json.dump(task.dict(), f, default=str)
    except Exception as e:
        logger.error(f"Failed to save task {task.task_id}: {e}")

def load_task(task_id: str) -> Optional[BackgroundTask]:
    """Load task from persistent storage"""
    try:
        task_file = TASK_STORAGE_DIR / f"{task_id}.json"
        if task_file.exists():
            with open(task_file, 'r') as f:
                data = json.load(f)
                # Convert datetime strings back to datetime objects
                for field in ['created_at', 'started_at', 'completed_at']:
                    if data.get(field):
                        data[field] = datetime.fromisoformat(data[field])
                return BackgroundTask(**data)
    except Exception as e:
        logger.error(f"Failed to load task {task_id}: {e}")
    return None

def delete_task_file(task_id: str):
    """Delete task file from storage"""
    try:
        task_file = TASK_STORAGE_DIR / f"{task_id}.json"
        if task_file.exists():
            task_file.unlink()
    except Exception as e:
        logger.error(f"Failed to delete task file {task_id}: {e}")

def create_task(task_type: str, user_id: str) -> str:
    """Create a new background task with persistent storage"""
    task_id = str(uuid.uuid4())
    task = BackgroundTask(
        task_id=task_id,
        task_type=task_type,
        user_id=user_id,
        status=TaskStatus.PENDING,
        created_at=datetime.utcnow()
    )
    save_task(task)
    logger.info(f"Created background task {task_id} of type {task_type} for user {user_id}")
    return task_id

def get_task(task_id: str) -> Optional[BackgroundTask]:
    """Get task status from persistent storage"""
    return load_task(task_id)

def update_task_progress(task_id: str, progress: int, message: str = None):
    """Update task progress with persistent storage"""
    task = load_task(task_id)
    if task:
        task.progress = progress
        if message:
            task.progress_message = message
        save_task(task)

def mark_task_started(task_id: str):
    """Mark task as started with persistent storage"""
    task = load_task(task_id)
    if task:
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        save_task(task)

def mark_task_completed(task_id: str, result: Dict = None):
    """Mark task as completed with persistent storage"""
    task = load_task(task_id)
    if task:
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        task.progress = 100
        task.progress_message = "Completed"
        if result:
            task.result = result
        save_task(task)
        logger.info(f"Task {task_id} completed successfully")

def mark_task_failed(task_id: str, error: str):
    """Mark task as failed with persistent storage"""
    task = load_task(task_id)
    if task:
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.utcnow()
        task.error = error
        save_task(task)
        logger.error(f"Task {task_id} failed: {error}")

async def run_task_async(task_id: str, coroutine):
    """
    Run a task asynchronously with proper error handling and cleanup
    """
    try:
        mark_task_started(task_id)
        
        # Execute the task
        result = await coroutine
        
        # Mark as completed
        mark_task_completed(task_id, result)
        
        # Schedule cleanup after a delay (don't block)
        asyncio.create_task(cleanup_task_after_delay(task_id, 300))  # 5 minutes
        
    except Exception as e:
        logger.error(f"Task {task_id} failed with error: {e}")
        mark_task_failed(task_id, str(e))
        # Still schedule cleanup for failed tasks
        asyncio.create_task(cleanup_task_after_delay(task_id, 300))

async def cleanup_task_after_delay(task_id: str, delay_seconds: int):
    """Clean up task file after a delay"""
    try:
        await asyncio.sleep(delay_seconds)
        delete_task_file(task_id)
        logger.info(f"Cleaned up task {task_id} after {delay_seconds} seconds")
    except Exception as e:
        logger.error(f"Error cleaning up task {task_id}: {e}")

def cleanup_old_tasks():
    """Clean up tasks older than 24 hours on startup"""
    try:
        cutoff_time = datetime.utcnow().timestamp() - (24 * 60 * 60)  # 24 hours ago
        
        for task_file in TASK_STORAGE_DIR.glob("*.json"):
            try:
                if task_file.stat().st_mtime < cutoff_time:
                    task_file.unlink()
                    logger.info(f"Cleaned up old task file: {task_file.name}")
            except Exception as e:
                logger.error(f"Error cleaning up task file {task_file}: {e}")
                
    except Exception as e:
        logger.error(f"Error during task cleanup: {e}")

# Initialize cleanup on import
cleanup_old_tasks() 