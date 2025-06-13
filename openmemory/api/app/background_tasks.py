"""
Background task management system for handling long-running operations.
"""
import asyncio
import uuid
from datetime import datetime, UTC
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
            # Convert to dict and handle enum serialization properly
            task_dict = task.model_dump()
            task_dict['status'] = task.status.value  # Convert enum to string value
            json.dump(task_dict, f, default=str)
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
                # Ensure status is converted properly
                if 'status' in data:
                    if isinstance(data['status'], str):
                        # Handle both old format (TaskStatus.PENDING) and new format (pending)
                        status_str = data['status']
                        if status_str.startswith('TaskStatus.'):
                            status_str = status_str.split('.')[1].lower()
                        data['status'] = TaskStatus(status_str)
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
        created_at=datetime.now(UTC)
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
        task.started_at = datetime.now(UTC)
        save_task(task)

def mark_task_completed(task_id: str, result: Dict = None):
    """Mark task as completed with persistent storage"""
    task = load_task(task_id)
    if task:
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(UTC)
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
        task.completed_at = datetime.now(UTC)
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
    """Clean up tasks older than 24 hours on startup and recover stuck tasks"""
    try:
        cutoff_time = datetime.now(UTC).timestamp() - (24 * 60 * 60)  # 24 hours ago
        stuck_cutoff = datetime.now(UTC).timestamp() - (2 * 60 * 60)  # 2 hours ago
        
        cleaned_count = 0
        recovered_count = 0
        
        for task_file in TASK_STORAGE_DIR.glob("*.json"):
            try:
                file_time = task_file.stat().st_mtime
                
                if file_time < cutoff_time:
                    # Delete old tasks
                    task_file.unlink()
                    cleaned_count += 1
                    logger.info(f"Cleaned up old task file: {task_file.name}")
                    
                elif file_time < stuck_cutoff:
                    # Try to recover stuck tasks
                    try:
                        with open(task_file, 'r') as f:
                            data = json.load(f)
                            
                        if data.get('status') in ['pending', 'running']:
                            # Mark stuck tasks as failed
                            data['status'] = 'failed'
                            data['error'] = 'Task recovery: Marked as failed due to system restart'
                            data['completed_at'] = datetime.now(UTC).isoformat()
                            
                            with open(task_file, 'w') as f:
                                json.dump(data, f, default=str)
                                
                            recovered_count += 1
                            logger.info(f"Recovered stuck task: {task_file.stem}")
                            
                    except Exception as e:
                        logger.error(f"Error recovering task {task_file}: {e}")
                        # If we can't recover it, delete it
                        task_file.unlink()
                        cleaned_count += 1
                        
            except Exception as e:
                logger.error(f"Error processing task file {task_file}: {e}")
                
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old task files")
        if recovered_count > 0:
            logger.info(f"Recovered {recovered_count} stuck tasks")
                
    except Exception as e:
        logger.error(f"Error during task cleanup: {e}")

def get_task_health_status() -> dict:
    """Get health status of the task system"""
    try:
        task_files = list(TASK_STORAGE_DIR.glob("*.json"))
        
        status_counts = {
            'pending': 0,
            'running': 0,
            'completed': 0,
            'failed': 0,
            'total': len(task_files)
        }
        
        stuck_tasks = []
        old_tasks = []
        
        current_time = datetime.now(UTC).timestamp()
        
        for task_file in task_files:
            try:
                with open(task_file, 'r') as f:
                    data = json.load(f)
                    
                status = data.get('status', 'unknown')
                if status in status_counts:
                    status_counts[status] += 1
                    
                # Check for stuck tasks (running for more than 2 hours)
                if status == 'running':
                    created_time = task_file.stat().st_mtime
                    if current_time - created_time > 7200:  # 2 hours
                        stuck_tasks.append(task_file.stem)
                        
                # Check for old completed tasks (older than 1 day)
                if status in ['completed', 'failed']:
                    created_time = task_file.stat().st_mtime
                    if current_time - created_time > 86400:  # 24 hours
                        old_tasks.append(task_file.stem)
                        
            except Exception as e:
                logger.error(f"Error reading task file {task_file}: {e}")
                
        return {
            'status_counts': status_counts,
            'stuck_tasks': stuck_tasks,
            'old_tasks': old_tasks,
            'storage_path': str(TASK_STORAGE_DIR),
            'healthy': len(stuck_tasks) == 0
        }
        
    except Exception as e:
        logger.error(f"Error getting task health status: {e}")
        return {
            'status_counts': {'error': 1},
            'stuck_tasks': [],
            'old_tasks': [],
            'storage_path': str(TASK_STORAGE_DIR),
            'healthy': False,
            'error': str(e)
        }

# Initialize cleanup on import
cleanup_old_tasks() 