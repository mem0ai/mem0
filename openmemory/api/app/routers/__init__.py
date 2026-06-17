from .apps import router as apps_router
from .backup import router as backup_router
from .compat_v3 import router as compat_v3_router
from .config import router as config_router
from .discovery import router as discovery_router
from .health import router as health_router
from .memories import router as memories_router
from .ops_metrics import router as ops_metrics_router
from .provision import router as provision_router
from .stats import router as stats_router

__all__ = [
    "memories_router",
    "apps_router",
    "stats_router",
    "config_router",
    "backup_router",
    "discovery_router",
    "compat_v3_router",
    "provision_router",
    "health_router",
    "ops_metrics_router",
]
