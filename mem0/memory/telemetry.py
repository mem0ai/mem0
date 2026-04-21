import atexit
import logging
import os
import platform
import random
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
_logger = logging.getLogger(__name__)


# Default sampling rate for hot-path OSS events. Lifecycle events always fire at 100%.
# Override via MEM0_TELEMETRY_SAMPLE_RATE env var.
_DEFAULT_SAMPLE_RATE = 0.1


def _parse_sample_rate(raw):
    """Parse MEM0_TELEMETRY_SAMPLE_RATE env var. Never raises."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        _logger.debug("MEM0_TELEMETRY_SAMPLE_RATE %r is not a number, defaulting to %s", raw, _DEFAULT_SAMPLE_RATE)
        return _DEFAULT_SAMPLE_RATE
    if not 0.0 <= value <= 1.0:
        _logger.debug("MEM0_TELEMETRY_SAMPLE_RATE %s out of [0.0, 1.0], defaulting to %s", value, _DEFAULT_SAMPLE_RATE)
        return _DEFAULT_SAMPLE_RATE
    return value


MEM0_TELEMETRY_SAMPLE_RATE = _parse_sample_rate(os.environ.get("MEM0_TELEMETRY_SAMPLE_RATE", str(_DEFAULT_SAMPLE_RATE)))

# Events that bypass sampling and always fire. Keep this set in sync with the
# event names passed to capture_event() in mem0/memory/main.py.
_LIFECYCLE_EVENTS = frozenset({"mem0.init", "mem0.reset", "mem0._create_procedural_memory"})


def _sampling_before_send(msg):
    """PostHog before_send hook: drop sampled hot-path events, annotate survivors with sample_rate."""
    if not isinstance(msg, dict):
        return None

    event_name = msg.get("event", "")
    is_lifecycle = event_name in _LIFECYCLE_EVENTS

    # >= so that rate=0 drops everything and rate=1 keeps everything (random ∈ [0, 1)).
    if not is_lifecycle and random.random() >= MEM0_TELEMETRY_SAMPLE_RATE:
        return None

    # Annotate so PostHog dashboards can extrapolate true counts via 1/sample_rate.
    properties = msg.setdefault("properties", {})
    properties["sample_rate"] = 1.0 if is_lifecycle else MEM0_TELEMETRY_SAMPLE_RATE
    return msg


class AnonymousTelemetry:
    def __init__(self, vector_store=None, before_send=None):
        if not MEM0_TELEMETRY:
            self.posthog = None
            self.user_id = None
            return

        try:
            self.posthog = Posthog(project_api_key=PROJECT_API_KEY, host=HOST, before_send=before_send)
        except TypeError:
            # posthog <4.5.0 does not accept before_send; fall back without sampling.
            _logger.debug("posthog.Posthog does not accept before_send; upgrade to >=4.5.0 for sampling")
            self.posthog = Posthog(project_api_key=PROJECT_API_KEY, host=HOST)
        self.user_id = get_or_create_user_id(vector_store)

    def capture_event(self, event_name, properties=None, user_email=None):
        if self.posthog is None:
            return

        # Determine distinct_id, skip if None to prevent crashes
        distinct_id = self.user_id if user_email is None else user_email
        if distinct_id is None:
            _logger.debug("Skipping telemetry event %r: no distinct_id available", event_name)
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
        try:
            self.posthog.capture(distinct_id=distinct_id, event=event_name, properties=properties)
        except Exception as e:
            _logger.debug("Failed to capture telemetry event %r: %s", event_name, e)

    def close(self):
        if self.posthog is not None:
            self.posthog.shutdown()
            self.posthog = None


# Thread-safe lazy singleton for OSS telemetry.
# A single AnonymousTelemetry instance (and its underlying PostHog client /
# background thread) is reused for the lifetime of the process instead of
# creating a new one on every capture_event() call.  The singleton is shut down
# once at process exit via an atexit handler.
_oss_telemetry_instance = None
_oss_telemetry_lock = threading.Lock()
_oss_telemetry_shutting_down = False


def _get_oss_telemetry():
    """Return the process-wide AnonymousTelemetry singleton, creating it on first call.

    Returns None after _shutdown_oss_telemetry() has run (interpreter exit).
    """
    global _oss_telemetry_instance
    if _oss_telemetry_shutting_down:
        return None
    if _oss_telemetry_instance is not None:
        return _oss_telemetry_instance

    with _oss_telemetry_lock:
        if _oss_telemetry_shutting_down:
            return None
        # Double-checked locking
        if _oss_telemetry_instance is not None:
            return _oss_telemetry_instance
        _oss_telemetry_instance = AnonymousTelemetry(before_send=_sampling_before_send)
        atexit.register(_shutdown_oss_telemetry)
        return _oss_telemetry_instance


def _shutdown_oss_telemetry():
    global _oss_telemetry_instance, _oss_telemetry_shutting_down
    with _oss_telemetry_lock:
        _oss_telemetry_shutting_down = True
        if _oss_telemetry_instance is not None:
            _oss_telemetry_instance.close()
            _oss_telemetry_instance = None


# Module-level client telemetry singleton (used by capture_client_event).
# No before_send — hosted MemoryClient traffic must never be sampled.
client_telemetry = AnonymousTelemetry()
atexit.register(client_telemetry.close)


def capture_event(event_name, memory_instance, additional_data=None):
    """Capture telemetry event for OSS Memory instances.

    This function is designed to never raise exceptions - telemetry failures
    should not affect the main application flow.
    """
    if not MEM0_TELEMETRY:
        return

    try:
        oss_telemetry = _get_oss_telemetry()
        if oss_telemetry is None:
            return

        event_data = {
            "collection": memory_instance.collection_name,
            "vector_size": memory_instance.embedding_model.config.embedding_dims,
            "history_store": "sqlite",
            "vector_store": f"{memory_instance.vector_store.__class__.__module__}.{memory_instance.vector_store.__class__.__name__}",
            "llm": f"{memory_instance.llm.__class__.__module__}.{memory_instance.llm.__class__.__name__}",
            "embedding_model": f"{memory_instance.embedding_model.__class__.__module__}.{memory_instance.embedding_model.__class__.__name__}",
            "function": f"{memory_instance.__class__.__module__}.{memory_instance.__class__.__name__}.{memory_instance.api_version}",
        }
        if additional_data:
            event_data.update(additional_data)

        oss_telemetry.capture_event(event_name, event_data)
    except Exception as e:
        _logger.debug("Failed to capture OSS telemetry event %r: %s", event_name, e)


def capture_client_event(event_name, instance, additional_data=None):
    """Capture telemetry event for hosted MemoryClient instances.

    This function is designed to never raise exceptions - telemetry failures
    should not affect the main application flow.
    """
    if not MEM0_TELEMETRY:
        return

    try:
        event_data = {
            "function": f"{instance.__class__.__module__}.{instance.__class__.__name__}",
        }
        if additional_data:
            event_data.update(additional_data)

        client_telemetry.capture_event(event_name, event_data, instance.user_email)
    except Exception as e:
        _logger.debug("Failed to capture client telemetry event %r: %s", event_name, e)
