import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock


class FakeMemory:
    def __init__(self, config):
        self.config = config

    @classmethod
    def from_config(cls, config):
        return cls(config)


class ServerStateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server_dir = Path(__file__).parent
        sys.path.insert(0, str(server_dir))
        sys.modules["mem0"] = types.SimpleNamespace(Memory=FakeMemory)
        cls.server_state = importlib.import_module("server_state")

    def test_refreshes_runtime_when_another_replica_updates_persisted_config(self):
        old_overrides = {
            "embedder": {"provider": "openai", "config": {"api_key": "old-key"}},
        }
        new_overrides = {
            "embedder": {"provider": "openai", "config": {"api_key": "new-key"}},
        }
        self.server_state._load_overrides = Mock(side_effect=[old_overrides, new_overrides])

        self.server_state.initialize_state({"version": "v1.1"})
        memory = self.server_state.get_memory_instance()

        self.assertEqual(memory.config["embedder"]["config"]["api_key"], "new-key")


if __name__ == "__main__":
    unittest.main()
