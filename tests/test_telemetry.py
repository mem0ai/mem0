import os
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4
from mem0 import Memory, MemoryClient
from mem0.memory.telemetry import capture_client_event, capture_event

def get_memory_instance():
    memory_instance = Mock(spec=Memory, collection_name="mock_collection")
    memory_instance.embedding_model = Mock(config=Mock(embedding_dims=128))
    memory_instance.vector_store = Mock(provider_name="mock_provider", config=Mock())
    memory_instance.llm = Mock(provider_name="mock_provider", config=Mock())
    memory_instance.version = "mock_version"
    return memory_instance

def get_memory_client_instance():
    memory_client_instance = Mock(spec=MemoryClient)
    return memory_client_instance

def use_telemetry():
    if os.getenv('TELEMETRY', "true").lower() == "true":
        # Capture Event 
        capture_event(
            event_name="mem0.add.function_call",
            memory_instance=get_memory_instance(),
            additional_data={"memory_id": uuid4(), "function_name": "add"}
        )
        
        # Capture Client Event
        capture_client_event(
            event_name="client.add", 
            instance=get_memory_client_instance()
        )
        return True
    return False


class TestTelemetry(unittest.TestCase):
    @patch.dict(os.environ, {'TELEMETRY': "true"})
    def test_telemetry_enabled(self):
        self.assertTrue(use_telemetry())

    @patch.dict(os.environ, {'TELEMETRY': "false"})
    def test_telemetry_disabled(self):
        self.assertFalse(use_telemetry())

    @patch.dict(os.environ, {}, clear=True)
    def test_telemetry_default_disabled(self):
        self.assertTrue(use_telemetry())

if __name__ == '__main__':
    unittest.main()

