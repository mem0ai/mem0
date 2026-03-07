import logging
import os
import platform
import sys
from threading import Lock

from posthog import Posthog

import mem0
from mem0.memory.setup import get_or_create_user_id

MEM0_TELEMETRY = os.environ.get("MEM0_TELEMETRY", "True")
PROJECT_API_KEY = "phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX"
HOST = "https://us.i.posthog.com"

if isinstance(MEM0_TELEMETRY, str):
    MEM0_TELEMETRY = MEM0_TELEMETRY.lower() in ("true", "1", "yes")

if not isinstance(MEM0_TELEMETRY, bool):
    raise ValueError("MEM0_TELEMETRY must be a boolean value.")

logging.getLogger("posthog").setLevel(logging.CRITICAL + 1)
logging.getLogger("urllib3").setLevel(logging.CRITICAL + 1)


# Cache for AnonymousTelemetry instances to avoid thread leaks
_telemetry_cache = {}
_telemetry_lock = Lock()


def _get_telemetry_instance(vector_store=None):
    """
    Get or create a cached AnonymousTelemetry instance for the given vector store.
    This prevents creating multiple Posthog instances that cause thread leaks.
    """
    if not MEM0_TELEMETRY:
        return None
    
    # Use vector store id as cache key, or None for default
    cache_key = id(vector_store) if vector_store else "default"
    
    with _telemetry_lock:
        if cache_key not in _telemetry_cache:
            _telemetry_cache[cache_key] = AnonymousTelemetry(vector_store)
        return _telemetry_cache[cache_key]


def shutdown_telemetry():
    """
    Shutdown all cached telemetry instances. Call this during application shutdown.
    """
    global _telemetry_cache
    with _telemetry_lock:
        for instance in _telemetry_cache.values():
            if instance is not None:
                instance.close()
        _telemetry_cache.clear()


class AnonymousTelemetry:
    def __init__(self, vector_store=None):
        if not MEM0_TELEMETRY:
            self.posthog = None
            self.user_id = None
            return

        self.posthog = Posthog(project_api_key=PROJECT_API_KEY, host=HOST)
        self.user_id = get_or_create_user_id(vector_store)

    def capture_event(self, event_name, properties=None, user_email=None):
        if self.posthog is None:
            return

        if properties is None:
            properties = {}
        properties = {
            "client_source": "python",
            "client_version": mem0.__version__,
            "python_version": sys.version,
            "os": sys.platform,
            "os_version": platform.version(),
            "os_release": platform.release(),
            "processor": platform.processor(),
            "machine": platform.machine(),
            **properties,
        }
        distinct_id = self.user_id if user_email is None else user_email
        self.posthog.capture(distinct_id=distinct_id, event=event_name, properties=properties)

    def close(self):
        if self.posthog is not None:
            self.posthog.shutdown()


client_telemetry = _get_telemetry_instance()


def capture_event(event_name, memory_instance, additional_data=None):
    if not MEM0_TELEMETRY:
        return

    oss_telemetry = _get_telemetry_instance(
        vector_store=memory_instance._telemetry_vector_store
        if hasattr(memory_instance, "_telemetry_vector_store")
        else None,
    )

    event_data = {
        "collection": memory_instance.collection_name,
        "vector_size": memory_instance.embedding_model.config.embedding_dims,
        "history_store": "sqlite",
        "graph_store": f"{memory_instance.graph.__class__.__module__}.{memory_instance.graph.__class__.__name__}"
        if memory_instance.config.graph_store.config
        else None,
        "vector_store": f"{memory_instance.vector_store.__class__.__module__}.{memory_instance.vector_store.__class__.__name__}",
        "llm": f"{memory_instance.llm.__class__.__module__}.{memory_instance.llm.__class__.__name__}",
        "embedding_model": f"{memory_instance.embedding_model.__class__.__module__}.{memory_instance.embedding_model.__class__.__name__}",
        "function": f"{memory_instance.__class__.__module__}.{memory_instance.__class__.__name__}.{memory_instance.api_version}",
    }
    if additional_data:
        event_data.update(additional_data)

    oss_telemetry.capture_event(event_name, event_data)


def capture_client_event(event_name, instance, additional_data=None):
    if not MEM0_TELEMETRY:
        return

    event_data = {
        "function": f"{instance.__class__.__module__}.{instance.__class__.__name__}",
    }
    if additional_data:
        event_data.update(additional_data)

    client_telemetry.capture_event(event_name, event_data, instance.user_email)
