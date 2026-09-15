"""Configuration API contract tests; run in the server image with unittest."""

import importlib
import os
import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient


class ConfigurationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        env = patch.dict(os.environ, {"ADMIN_API_KEY": "configuration-test-admin-key", "MEM0_TELEMETRY": "false"})
        env.start()
        cls.addClassCleanup(env.stop)
        memory = patch("mem0.Memory.from_config", return_value=Mock())
        memory.start()
        cls.addClassCleanup(memory.stop)
        load = patch("server_state._load_overrides", return_value={})
        load.start()
        cls.addClassCleanup(load.stop)
        cls.main = importlib.import_module("main")
        cls.state = importlib.import_module("server_state")
        request_log = patch.object(cls.main, "_persist_request_log")
        request_log.start()
        cls.addClassCleanup(request_log.stop)
        dependencies = patch.dict(
            cls.main.app.dependency_overrides,
            {
                cls.main.verify_auth: lambda: None,
                cls.main.require_admin: lambda: None,
            },
        )
        dependencies.start()
        cls.addClassCleanup(dependencies.stop)

    def setUp(self):
        self.saved = {}
        load = patch.object(self.state, "_load_overrides", side_effect=lambda: deepcopy(self.saved))
        load.start()
        self.addCleanup(load.stop)
        save = patch.object(self.state, "_save_overrides", side_effect=self.save_overrides)
        save.start()
        self.addCleanup(save.stop)
        self.state.initialize_state(
            {
                "llm": {"provider": "openai", "config": {"api_key": "test-original-key", "model": "test-model"}},
                "embedder": {"provider": "openai", "config": {}},
            }
        )
        self.client = TestClient(self.main.app)
        self.addCleanup(self.client.close)

    def save_overrides(self, config):
        self.saved = deepcopy(config)

    def get_config(self):
        response = self.client.get("/configure")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_reports_presence_without_disclosing_or_mutating_secrets(self):
        config = self.get_config()
        self.assertIs(config["llm"]["config"]["api_key_set"], True)
        self.assertEqual(config["llm"]["config"]["api_key"], "[redacted]")
        self.assertIs(config["embedder"]["config"]["api_key_set"], False)
        current = self.state.get_current_config()["llm"]["config"]
        self.assertEqual(current["api_key"], "test-original-key")
        self.assertNotIn("api_key_set", current)

    def test_absent_empty_and_null_keys_report_false(self):
        for settings in [{}, {"api_key": ""}, {"api_key": None}]:
            with self.subTest(settings=settings):
                self.state.initialize_state({"llm": {"provider": "openai", "config": settings}})
                self.assertIs(self.get_config()["llm"]["config"]["api_key_set"], False)

    def test_blank_or_unchanged_keys_preserve_existing_value(self):
        for key in [None, "", "   ", "[redacted]"]:
            with self.subTest(key=key):
                response = self.client.post(
                    "/configure",
                    json={
                        "llm": {
                            "provider": "openai",
                            "config": {
                                "api_key": key,
                                "api_key_set": False,
                                "model": "updated-model",
                            },
                        },
                    },
                )
                self.assertEqual(response.status_code, 200)
                current = self.state.get_current_config()["llm"]["config"]
                self.assertEqual(current["api_key"], "test-original-key")
                self.assertEqual(current["model"], "updated-model")
                self.assertNotIn("api_key_set", self.saved["llm"]["config"])

    def test_provider_round_trip_does_not_replace_secret_with_redaction_marker(self):
        config = self.get_config()
        response = self.client.post("/configure", json={name: config[name] for name in ("llm", "embedder")})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.state.get_current_config()["llm"]["config"]["api_key"], "test-original-key")
        self.assertNotIn("api_key_set", self.saved["embedder"]["config"])

    def test_replacement_is_saved_and_remains_redacted(self):
        response = self.client.post(
            "/configure",
            json={
                "embedder": {"provider": "openai", "config": {"api_key": "test-replacement-key"}},
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.saved["embedder"]["config"]["api_key"], "test-replacement-key")
        config = self.get_config()["embedder"]["config"]
        self.assertIs(config["api_key_set"], True)
        self.assertEqual(config["api_key"], "[redacted]")


if __name__ == "__main__":
    unittest.main()
