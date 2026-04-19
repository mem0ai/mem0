from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "Agent Memory Runtime"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/v1"
    api_port: int = 8080
    worker_poll_seconds: float = 2.0
    worker_stale_after_seconds: float = 30.0
    stalled_job_after_seconds: float = 60.0
    postgres_dsn: str = "sqlite+pysqlite:///./memory_runtime.db"
    redis_url: str = "redis://localhost:6379/0"
    auto_create_tables: bool = True
    mem0_bridge_enabled: bool = False
    mem0_base_url: str | None = None
    mem0_api_key: str | None = None
    mem0_timeout_seconds: float = 5.0

    @property
    def database_url(self) -> str:
        return self.postgres_dsn


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("MEMORY_RUNTIME_APP_NAME", "Agent Memory Runtime"),
        environment=os.getenv("MEMORY_RUNTIME_ENV", "development"),
        debug=_to_bool(os.getenv("MEMORY_RUNTIME_DEBUG"), default=False),
        api_prefix=os.getenv("MEMORY_RUNTIME_API_PREFIX", "/v1"),
        api_port=int(os.getenv("MEMORY_RUNTIME_API_PORT", "8080")),
        worker_poll_seconds=float(os.getenv("MEMORY_RUNTIME_WORKER_POLL_SECONDS", "2.0")),
        worker_stale_after_seconds=float(os.getenv("MEMORY_RUNTIME_WORKER_STALE_AFTER_SECONDS", "30.0")),
        stalled_job_after_seconds=float(os.getenv("MEMORY_RUNTIME_STALLED_JOB_AFTER_SECONDS", "60.0")),
        postgres_dsn=os.getenv(
            "MEMORY_RUNTIME_POSTGRES_DSN",
            "sqlite+pysqlite:///./memory_runtime.db",
        ),
        redis_url=os.getenv("MEMORY_RUNTIME_REDIS_URL", "redis://localhost:6379/0"),
        auto_create_tables=_to_bool(os.getenv("MEMORY_RUNTIME_AUTO_CREATE_TABLES"), default=True),
        mem0_bridge_enabled=_to_bool(os.getenv("MEMORY_RUNTIME_MEM0_BRIDGE_ENABLED"), default=False),
        mem0_base_url=os.getenv("MEMORY_RUNTIME_MEM0_BASE_URL"),
        mem0_api_key=os.getenv("MEMORY_RUNTIME_MEM0_API_KEY"),
        mem0_timeout_seconds=float(os.getenv("MEMORY_RUNTIME_MEM0_TIMEOUT_SECONDS", "5.0")),
    )
