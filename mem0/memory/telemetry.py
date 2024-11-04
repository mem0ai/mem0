import logging
import os
import platform
import sys

from posthog import Posthog

import mem0
from mem0.memory.setup import get_user_id, setup_config

MEM0_TELEMETRY = os.environ.get("MEM0_TELEMETRY", "True")

if isinstance(MEM0_TELEMETRY, str):
    MEM0_TELEMETRY = MEM0_TELEMETRY.lower() in ("true", "1", "yes")

if not isinstance(MEM0_TELEMETRY, bool):
    raise ValueError("MEM0_TELEMETRY must be a boolean value.")

logging.getLogger("posthog").setLevel(logging.CRITICAL + 1)
logging.getLogger("urllib3").setLevel(logging.CRITICAL + 1)


class AnonymousTelemetry:
    def __init__(self, project_api_key, host):
        self.posthog = Posthog(project_api_key=project_api_key, host=host)
        # Call setup config to ensure that the user_id is generated
        setup_config()
        self.user_id = get_user_id()
        if not MEM0_TELEMETRY:
            self.posthog.disabled = True

    def capture_event(self, event_name, properties=None):
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
        self.posthog.capture(distinct_id=self.user_id, event=event_name, properties=properties)

    def close(self):
        self.posthog.shutdown()


# Initialize AnonymousTelemetry
telemetry = AnonymousTelemetry(
    project_api_key="phc_hgJkUVJFYtmaJqrvf6CYN67TIQ8yhXAkWzUn9AMU4yX",
    host="https://us.i.posthog.com",
)


def capture_event(event_name, memory_instance, additional_data=None):
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

    telemetry.capture_event(event_name, event_data)


def capture_client_event(event_name, instance, additional_data=None):
    event_data = {
        "function": f"{instance.__class__.__module__}.{instance.__class__.__name__}",
    }
    if additional_data:
        event_data.update(additional_data)

    telemetry.capture_event(event_name, event_data)
