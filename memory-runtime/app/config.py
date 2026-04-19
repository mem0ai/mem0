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
    postgres_dsn: str = "postgresql://postgres:postgres@localhost:5432/memory_runtime"
    redis_url: str = "redis://localhost:6379/0"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_name=os.getenv("MEMORY_RUNTIME_APP_NAME", "Agent Memory Runtime"),
        environment=os.getenv("MEMORY_RUNTIME_ENV", "development"),
        debug=_to_bool(os.getenv("MEMORY_RUNTIME_DEBUG"), default=False),
        api_prefix=os.getenv("MEMORY_RUNTIME_API_PREFIX", "/v1"),
        api_port=int(os.getenv("MEMORY_RUNTIME_API_PORT", "8080")),
        postgres_dsn=os.getenv(
            "MEMORY_RUNTIME_POSTGRES_DSN",
            "postgresql://postgres:postgres@localhost:5432/memory_runtime",
        ),
        redis_url=os.getenv("MEMORY_RUNTIME_REDIS_URL", "redis://localhost:6379/0"),
    )
