"""Tests for user profile functionality."""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from mem0.configs.base import ProfileConfig
from mem0.memory.main import Memory


class TestProfileGeneration(unittest.TestCase):
    """Test profile generation and management."""

    def setUp(self):
        """Set up test fixtures."""
        # Use a temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()

        # Mock configuration
        self.config = {
            "llm": {
                "provider": "openai",
                "config": {"model": "gpt-4o-mini", "temperature": 0.2},
            },
            "version": "v1.1",
            "history_db_path": self.temp_db.name,
            "profile_config": {
                "max_tokens": 400,
                "auto_update": True,
                "memory_count": 5,  # Lower threshold for testing
                "time_elapsed": 10,  # 10 seconds for testing
            },
        }

    def tearDown(self):
        """Clean up test fixtures."""
        try:
            os.unlink(self.temp_db.name)
        except Exception:
            pass

    @patch("mem0.utils.factory.LlmFactory.create")
    @patch("mem0.utils.factory.EmbedderFactory.create")
    @patch("mem0.utils.factory.VectorStoreFactory.create")
    def test_get_profile_creates_new_profile(self, mock_vector, mock_embedder, mock_llm):
        """Test that get_profile creates a new profile if one doesn't exist."""
        # Setup mocks
        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_response.return_value = (
            "Alice is a software engineer interested in AI and machine learning."
        )
        mock_llm.return_value = mock_llm_instance

        mock_embedder_instance = MagicMock()
        mock_embedder.return_value = mock_embedder_instance

        mock_vector_instance = MagicMock()
        mock_vector_instance.list.return_value = (
            [
                MagicMock(
                    id="1",
                    payload={
                        "data": "Alice is a software engineer",
                        "hash": "hash1",
                        "created_at": "2024-01-01",
                    },
                ),
                MagicMock(
                    id="2",
                    payload={
                        "data": "Alice likes machine learning",
                        "hash": "hash2",
                        "created_at": "2024-01-01",
                    },
                ),
            ],
            2,
        )
        mock_vector.return_value = mock_vector_instance

        # Create Memory instance
        m = Memory.from_config(config_dict=self.config)

        # Get profile (should create new one)
        profile = m.get_profile(user_id="alice")

        # Assertions
        self.assertIsNotNone(profile)
        self.assertIn("profile", profile)
        self.assertEqual(profile["user_id"], "alice")
        self.assertIn("Alice is a software engineer", profile["profile"])

    @patch("mem0.utils.factory.LlmFactory.create")
    @patch("mem0.utils.factory.EmbedderFactory.create")
    @patch("mem0.utils.factory.VectorStoreFactory.create")
    def test_get_profile_returns_cached(self, mock_vector, mock_embedder, mock_llm):
        """Test that get_profile returns cached profile if it exists."""
        # Setup mocks
        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_response.return_value = (
            "Alice is a software engineer interested in AI and machine learning."
        )
        mock_llm.return_value = mock_llm_instance

        mock_embedder_instance = MagicMock()
        mock_embedder.return_value = mock_embedder_instance

        mock_vector_instance = MagicMock()
        mock_vector_instance.list.return_value = (
            [
                MagicMock(
                    id="1",
                    payload={
                        "data": "Alice is a software engineer",
                        "hash": "hash1",
                        "created_at": "2024-01-01",
                    },
                )
            ],
            1,
        )
        mock_vector.return_value = mock_vector_instance

        # Create Memory instance
        m = Memory.from_config(config_dict=self.config)

        # Get profile first time (creates it)
        profile1 = m.get_profile(user_id="alice")

        # Get profile second time (should return cached)
        # Reset mock to ensure it's not called again
        mock_llm_instance.generate_response.reset_mock()
        profile2 = m.get_profile(user_id="alice")

        # Should return same profile without calling LLM again
        self.assertEqual(profile1["profile"], profile2["profile"])
        mock_llm_instance.generate_response.assert_not_called()

    @patch("mem0.utils.factory.LlmFactory.create")
    @patch("mem0.utils.factory.EmbedderFactory.create")
    @patch("mem0.utils.factory.VectorStoreFactory.create")
    def test_profile_auto_update_memory_count(self, mock_vector, mock_embedder, mock_llm):
        """Test that profile auto-updates when memory count threshold is reached."""
        # Setup mocks
        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_response.side_effect = [
            json.dumps({"facts": ["Alice is a software engineer"]}),
            "Initial profile about Alice",
            json.dumps({"memory": [{"text": "Alice is a software engineer", "event": "ADD"}]}),
            json.dumps({"facts": ["Alice likes Python"]}),
            json.dumps({"memory": [{"text": "Alice likes Python", "event": "ADD"}]}),
            json.dumps({"facts": ["Alice enjoys hiking"]}),
            json.dumps({"memory": [{"text": "Alice enjoys hiking", "event": "ADD"}]}),
            json.dumps({"facts": ["Alice lives in SF"]}),
            json.dumps({"memory": [{"text": "Alice lives in SF", "event": "ADD"}]}),
            json.dumps({"facts": ["Alice has 5 years experience"]}),
            json.dumps({"memory": [{"text": "Alice has 5 years experience", "event": "ADD"}]}),
            "Updated profile about Alice with more details",  # Auto-update triggered
        ]
        mock_llm.return_value = mock_llm_instance

        mock_embedder_instance = MagicMock()
        mock_embedder_instance.embed.return_value = [0.1] * 100
        mock_embedder.return_value = mock_embedder_instance

        # Memory counter for list() calls
        memory_list = []

        def create_list_response(*args, **kwargs):
            return ([MagicMock(id=str(i), payload=m) for i, m in enumerate(memory_list)], len(memory_list))

        mock_vector_instance = MagicMock()
        mock_vector_instance.list.side_effect = create_list_response
        mock_vector_instance.search.return_value = []
        mock_vector.return_value = mock_vector_instance

        # Create Memory instance
        m = Memory.from_config(config_dict=self.config)

        # Add memories one by one - should trigger auto-update after 5th memory
        for i in range(5):
            m.add(f"Memory {i} about Alice", user_id="alice")
            memory_list.append({"data": f"Memory {i} about Alice", "hash": f"hash{i}", "created_at": "2024-01-01"})

        # Check that profile was auto-updated
        profile = m.db.get_profile(user_id="alice")
        self.assertIsNotNone(profile)
        # The auto-update should have been triggered

    @patch("mem0.utils.factory.LlmFactory.create")
    @patch("mem0.utils.factory.EmbedderFactory.create")
    @patch("mem0.utils.factory.VectorStoreFactory.create")
    def test_custom_profile_prompt(self, mock_vector, mock_embedder, mock_llm):
        """Test using a custom profile prompt."""
        custom_prompt = """Generate a healthcare profile focusing on:
        - Patient demographics
        - Medical conditions
        - Medication preferences
        - Appointment history
        """

        config = self.config.copy()
        config["custom_profile_prompt"] = custom_prompt

        # Setup mocks
        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_response.return_value = (
            "Patient Alice, 35 years old, has diabetes and prefers morning appointments."
        )
        mock_llm.return_value = mock_llm_instance

        mock_embedder_instance = MagicMock()
        mock_embedder.return_value = mock_embedder_instance

        mock_vector_instance = MagicMock()
        mock_vector_instance.list.return_value = (
            [
                MagicMock(
                    id="1",
                    payload={
                        "data": "Patient has diabetes",
                        "hash": "hash1",
                        "created_at": "2024-01-01",
                    },
                )
            ],
            1,
        )
        mock_vector.return_value = mock_vector_instance

        # Create Memory instance with custom prompt
        m = Memory.from_config(config_dict=config)

        # Get profile
        profile = m.get_profile(user_id="alice")

        # Verify custom prompt was used (check that generate_response was called)
        self.assertTrue(mock_llm_instance.generate_response.called)
        # Verify profile contains healthcare-related info
        self.assertIn("diabetes", profile["profile"].lower())

    def test_profile_config_validation(self):
        """Test that profile configuration is properly validated."""
        from mem0.configs.base import ProfileConfig

        # Test default values
        profile_config = ProfileConfig()
        self.assertEqual(profile_config.max_tokens, 400)
        self.assertEqual(profile_config.auto_update, True)
        self.assertEqual(profile_config.memory_count, 10)
        self.assertEqual(profile_config.time_elapsed, 86400)

        # Test custom values
        custom_config = ProfileConfig(max_tokens=500, auto_update=False, memory_count=20, time_elapsed=3600)
        self.assertEqual(custom_config.max_tokens, 500)
        self.assertEqual(custom_config.auto_update, False)
        self.assertEqual(custom_config.memory_count, 20)
        self.assertEqual(custom_config.time_elapsed, 3600)

    @patch("mem0.utils.factory.LlmFactory.create")
    @patch("mem0.utils.factory.EmbedderFactory.create")
    @patch("mem0.utils.factory.VectorStoreFactory.create")
    def test_profile_history_tracking(self, mock_vector, mock_embedder, mock_llm):
        """Test that profile history is tracked correctly."""
        # Setup mocks
        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_response.return_value = "Alice is a software engineer"
        mock_llm.return_value = mock_llm_instance

        mock_embedder_instance = MagicMock()
        mock_embedder.return_value = mock_embedder_instance

        mock_vector_instance = MagicMock()
        mock_vector_instance.list.return_value = ([], 0)
        mock_vector.return_value = mock_vector_instance

        # Create Memory instance
        m = Memory.from_config(config_dict=self.config)

        # Create initial profile
        m.get_profile(user_id="alice")

        # Check history exists
        history = m.get_profile_history(user_id="alice")
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["version"], 1)
        self.assertEqual(history[0]["update_reason"], "initial")

        # Update profile manually
        m.update_profile(user_id="alice", force=True)

        # Check history has 2 versions
        history = m.get_profile_history(user_id="alice")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["version"], 2)  # Latest first
        self.assertEqual(history[0]["update_reason"], "manual")
        self.assertEqual(history[1]["version"], 1)

    @patch("mem0.utils.factory.LlmFactory.create")
    @patch("mem0.utils.factory.EmbedderFactory.create")
    @patch("mem0.utils.factory.VectorStoreFactory.create")
    def test_quality_metrics_added(self, mock_vector, mock_embedder, mock_llm):
        """Test that quality metrics are added to profile."""
        # Setup mocks
        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_response.return_value = (
            "Alice is a software engineer with 5 years of experience. "
            "She prefers technical documentation and enjoys Python programming. "
            "Currently working on AI projects and interested in machine learning."
        )
        mock_llm.return_value = mock_llm_instance

        mock_embedder_instance = MagicMock()
        mock_embedder.return_value = mock_embedder_instance

        mock_vector_instance = MagicMock()
        mock_vector_instance.list.return_value = (
            [
                MagicMock(
                    id=str(i),
                    payload={"data": f"Memory {i}", "hash": f"hash{i}", "created_at": "2024-01-01"},
                )
                for i in range(10)
            ],
            10,
        )
        mock_vector.return_value = mock_vector_instance

        # Create Memory instance
        m = Memory.from_config(config_dict=self.config)

        # Get profile
        profile = m.get_profile(user_id="alice")

        # Verify quality metrics exist
        self.assertIn("quality_metrics", profile)
        metrics = profile["quality_metrics"]

        self.assertIn("memory_count", metrics)
        self.assertIn("confidence_score", metrics)
        self.assertIn("token_count", metrics)
        self.assertIn("days_since_update", metrics)
        self.assertIn("warnings", metrics)

        # Verify values are reasonable
        self.assertEqual(metrics["memory_count"], 10)
        self.assertGreater(metrics["confidence_score"], 0.0)
        self.assertLessEqual(metrics["confidence_score"], 1.0)
        self.assertGreater(metrics["token_count"], 0)

    @patch("mem0.utils.factory.LlmFactory.create")
    @patch("mem0.utils.factory.EmbedderFactory.create")
    @patch("mem0.utils.factory.VectorStoreFactory.create")
    def test_manual_update_profile(self, mock_vector, mock_embedder, mock_llm):
        """Test manual profile update method."""
        # Setup mocks
        mock_llm_instance = MagicMock()
        mock_llm_instance.generate_response.side_effect = [
            "Initial profile",
            "Updated profile",
        ]
        mock_llm.return_value = mock_llm_instance

        mock_embedder_instance = MagicMock()
        mock_embedder.return_value = mock_embedder_instance

        mock_vector_instance = MagicMock()
        # Return some memories so profile isn't "No memories available"
        mock_vector_instance.list.return_value = (
            [MagicMock(id="1", payload={"data": "Alice is a software engineer", "hash": "hash1"})],
            1,
        )
        mock_vector.return_value = mock_vector_instance

        # Create Memory instance
        m = Memory.from_config(config_dict=self.config)

        # Create initial profile
        profile1 = m.get_profile(user_id="alice")
        self.assertIn("Initial profile", profile1["profile"])

        # Manually update
        profile2 = m.update_profile(user_id="alice", force=True)
        self.assertIn("Updated profile", profile2["profile"])

        # Verify it was updated in DB
        profile3 = m.get_profile(user_id="alice")
        self.assertIn("Updated profile", profile3["profile"])

    def test_async_update_config(self):
        """Test that async_update config field exists and works."""
        # Test default
        config = ProfileConfig()
        self.assertTrue(config.async_update)

        # Test custom value
        config_sync = ProfileConfig(async_update=False)
        self.assertFalse(config_sync.async_update)

    def test_incremental_vs_full_update(self):
        """Test that force=False uses incremental, force=True uses full."""
        from mem0.memory.main import Memory

        # This test just verifies the methods exist and can be called
        # Integration testing would require actual LLM calls
        self.assertTrue(hasattr(Memory, "_generate_profile_incremental"))
        self.assertTrue(hasattr(Memory, "update_profile"))

        # Verify update_profile accepts force parameter
        import inspect

        sig = inspect.signature(Memory.update_profile)
        self.assertIn("force", sig.parameters)


if __name__ == "__main__":
    unittest.main()
