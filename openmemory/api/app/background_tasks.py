import asyncio
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class BackgroundTask:
    def __init__(self, task_id: str, task_type: str, user_id: str):
        self.task_id = task_id
        self.task_type = task_type
        self.user_id = user_id
        self.status = TaskStatus.PENDING
        self.progress = 0
        self.progress_message = ""
        self.created_at = datetime.utcnow()
        self.started_at = None
        self.completed_at = None
        self.result = None
        self.error = None

# In-memory task storage (replace with Redis in production)
_tasks: Dict[str, BackgroundTask] = {}

def create_task(task_type: str, user_id: str) -> str:
    """Create a new background task and return its ID"""
    task_id = str(uuid.uuid4())
    task = BackgroundTask(task_id, task_type, user_id)
    _tasks[task_id] = task
    logger.info(f"Created background task {task_id} of type {task_type} for user {user_id}")
    return task_id

def get_task(task_id: str) -> Optional[BackgroundTask]:
    """Get a task by ID"""
    return _tasks.get(task_id)

def update_task_progress(task_id: str, progress: int, message: str = ""):
    """Update task progress"""
    if task_id in _tasks:
        task = _tasks[task_id]
        task.progress = progress
        task.progress_message = message
        if task.status == TaskStatus.PENDING:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
        logger.debug(f"Task {task_id} progress: {progress}% - {message}")

def complete_task(task_id: str, result: Dict[str, Any]):
    """Mark a task as completed with result"""
    task = _tasks.get(task_id)
    if task:
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        task.result = result

def fail_task(task_id: str, error: str):
    """Mark a task as failed with error"""
    task = _tasks.get(task_id)
    if task:
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.utcnow()
        task.error = error

async def run_task_async(task_id: str, coro):
    """Run an async task and update its status"""
    if task_id not in _tasks:
        logger.error(f"Task {task_id} not found")
        return
    
    task = _tasks[task_id]
    try:
        logger.info(f"Starting execution of task {task_id}")
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        
        result = await coro
        
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        task.result = result
        task.progress = 100
        task.progress_message = "Completed successfully"
        logger.info(f"Task {task_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Task {task_id} failed with error: {e}")
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.utcnow()
        task.error = str(e)
        task.progress_message = f"Failed: {str(e)}"

def cleanup_old_tasks(hours: int = 24) -> int:
    """Clean up tasks older than specified hours"""
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    to_remove = []
    
    for task_id, task in _tasks.items():
        if task.created_at < cutoff_time:
            to_remove.append(task_id)
    
    for task_id in to_remove:
        del _tasks[task_id]
        logger.debug(f"Cleaned up old task {task_id}")
    
    if to_remove:
        logger.info(f"Cleaned up {len(to_remove)} old background tasks")
    
    return len(to_remove) 