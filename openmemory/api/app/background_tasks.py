import asyncio
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
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
        self.created_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None
        self.progress: int = 0
        self.progress_message: str = ""

# In-memory task storage (replace with Redis in production)
_tasks: Dict[str, BackgroundTask] = {}

def create_task(task_type: str, user_id: str) -> str:
    """Create a new background task and return its ID"""
    task_id = str(uuid.uuid4())
    task = BackgroundTask(task_id, task_type, user_id)
    _tasks[task_id] = task
    return task_id

def get_task(task_id: str) -> Optional[BackgroundTask]:
    """Get a task by ID"""
    return _tasks.get(task_id)

def update_task_progress(task_id: str, progress: int, message: str = ""):
    """Update task progress"""
    task = _tasks.get(task_id)
    if task:
        task.progress = progress
        task.progress_message = message

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

async def run_task_async(task_id: str, coroutine):
    """Run an async task in the background"""
    task = _tasks.get(task_id)
    if not task:
        return
    
    task.status = TaskStatus.RUNNING
    task.started_at = datetime.utcnow()
    
    try:
        result = await coroutine
        complete_task(task_id, result)
    except Exception as e:
        logger.error(f"Background task {task_id} failed: {e}")
        fail_task(task_id, str(e))

def cleanup_old_tasks(hours: int = 24):
    """Remove tasks older than specified hours"""
    cutoff = datetime.utcnow()
    to_remove = []
    
    for task_id, task in _tasks.items():
        if task.completed_at:
            age = (cutoff - task.completed_at).total_seconds() / 3600
            if age > hours:
                to_remove.append(task_id)
    
    for task_id in to_remove:
        del _tasks[task_id]
    
    return len(to_remove) 