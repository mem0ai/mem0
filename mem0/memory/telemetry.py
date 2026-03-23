import atexit
import logging
import os
import platform
import sys
import threading

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


# Thread-safe lazy singletons
_telemetry_lock = threading.Lock()
_oss_telemetry = None
_client_telemetry = None


def _get_oss_telemetry(vector_store=None):
    """Return the singleton OSS telemetry instance, creating it on first call.

    The vector_store parameter is only used on the first call for
    get_or_create_user_id(). Subsequent calls reuse the existing instance
    since the user ID is stable once created.
    """
    global _oss_telemetry
    if _oss_telemetry is None:
        with _telemetry_lock:
            if _oss_telemetry is None:
                _oss_telemetry = AnonymousTelemetry(vector_store=vector_store)
    return _oss_telemetry


def _get_client_telemetry():
    """Return the singleton client telemetry instance, creating it on first call."""
    global _client_telemetry
    if _client_telemetry is None:
        with _telemetry_lock:
            if _client_telemetry is None:
                _client_telemetry = AnonymousTelemetry()
    return _client_telemetry


def shutdown_telemetry():
    """Shut down all telemetry singletons. Safe to call multiple times.

    Singletons are lazily re-created on next use, so this is safe even
    when multiple Memory instances exist.
    """
    global _oss_telemetry, _client_telemetry
    with _telemetry_lock:
        if _oss_telemetry is not None:
            _oss_telemetry.close()
            _oss_telemetry = None
        if _client_telemetry is not None:
            _client_telemetry.close()
            _client_telemetry = None


atexit.register(shutdown_telemetry)


def capture_event(event_name, memory_instance, additional_data=None):
    if not MEM0_TELEMETRY:
        return

    vector_store = getattr(memory_instance, "_telemetry_vector_store", None)
    oss_telemetry = _get_oss_telemetry(vector_store=vector_store)

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

    client_telemetry = _get_client_telemetry()

    event_data = {
        "function": f"{instance.__class__.__module__}.{instance.__class__.__name__}",
    }
    if additional_data:
        event_data.update(additional_data)

    client_telemetry.capture_event(event_name, event_data, instance.user_email)
