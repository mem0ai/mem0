import platform
import sys

from posthog import Posthog

from mem0.memory.setup import get_user_id, setup_config


class AnonymousTelemetry:
    def __init__(self, project_api_key, host):
        self.posthog = Posthog(project_api_key=project_api_key, host=host)
        # Call setup config to ensure that the user_id is generated
        setup_config()
        self.user_id = get_user_id()

    def capture_event(self, event_name, properties=None):
        if properties is None:
            properties = {}
        properties = {
            "python_version": sys.version,
            "os": sys.platform,
            "os_version": platform.version(),
            "os_release": platform.release(),
            "processor": platform.processor(),
            "machine": platform.machine(),
            **properties,
        }
        self.posthog.capture(
            distinct_id=self.user_id, event=event_name, properties=properties
        )

    def identify_user(self, user_id, properties=None):
        if properties is None:
            properties = {}
        self.posthog.identify(distinct_id=user_id, properties=properties)

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
        "vector_size": memory_instance.embedding_model.dims,
        "history_store": "sqlite",
        "vector_store": f"{memory_instance.vector_store.__class__.__module__}.{memory_instance.vector_store.__class__.__name__}",
        "llm": f"{memory_instance.llm.__class__.__module__}.{memory_instance.llm.__class__.__name__}",
        "embedding_model": f"{memory_instance.embedding_model.__class__.__module__}.{memory_instance.embedding_model.__class__.__name__}",
        "function": f"{memory_instance.__class__.__module__}.{memory_instance.__class__.__name__}",
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
