"""Models package containing database models and API schemas.

This __init__.py re-exports both:
- Database models from ../models.py (SQLAlchemy)
- API schemas from ./schemas.py (Pydantic)
"""

# Re-export database models from parent models.py
import sys
from pathlib import Path
parent_dir = str(Path(__file__).parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import database models from app.models module (the .py file, not this package)
import importlib.util
spec = importlib.util.spec_from_file_location("db_models", Path(__file__).parent.parent / "models.py")
db_models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db_models)

# Re-export database models
User = db_models.User
App = db_models.App
Memory = db_models.Memory
MemoryState = db_models.MemoryState
MemoryStatusHistory = db_models.MemoryStatusHistory
MemoryAccessLog = db_models.MemoryAccessLog
AccessControl = db_models.AccessControl
Category = db_models.Category
Prompt = db_models.Prompt
PromptType = db_models.PromptType
Config = db_models.Config
ArchivePolicy = db_models.ArchivePolicy
memory_categories = db_models.memory_categories

# Re-export API schemas
from .schemas import (
    TimeRange,
    TemporalEntity,
    CreateMemoryRequest,
    DeleteMemoriesRequest,
    PauseMemoriesRequest,
    UpdateMemoryRequest,
    MoveMemoriesRequest,
    FilterMemoriesRequest,
)

__all__ = [
    # Database models
    "User",
    "App",
    "Memory",
    "MemoryState",
    "MemoryStatusHistory",
    "MemoryAccessLog",
    "AccessControl",
    "Category",
    "Prompt",
    "PromptType",
    "Config",
    "ArchivePolicy",
    "memory_categories",
    # API schemas
    "TimeRange",
    "TemporalEntity",
    "CreateMemoryRequest",
    "DeleteMemoriesRequest",
    "PauseMemoriesRequest",
    "UpdateMemoryRequest",
    "MoveMemoriesRequest",
    "FilterMemoriesRequest",
]

