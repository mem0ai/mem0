from .apps import router as apps_router
from .backup import router as backup_router
from .config import router as config_router
from .graph import router as graph_router
from .memories import router as memories_router
from .prompts import router as prompts_router
from .stats import router as stats_router

__all__ = ["memories_router", "apps_router", "stats_router", "config_router", "backup_router", "prompts_router", "graph_router"]
