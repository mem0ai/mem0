import os
import unittest

from app.config import Settings, get_settings


class SettingsTests(unittest.TestCase):
    def tearDown(self) -> None:
        for key in (
            "MEMORY_RUNTIME_APP_NAME",
            "MEMORY_RUNTIME_ENV",
            "MEMORY_RUNTIME_DEBUG",
            "MEMORY_RUNTIME_API_PREFIX",
            "MEMORY_RUNTIME_API_PORT",
            "MEMORY_RUNTIME_POSTGRES_DSN",
            "MEMORY_RUNTIME_REDIS_URL",
        ):
            os.environ.pop(key, None)
        get_settings.cache_clear()

    def test_default_settings(self) -> None:
        get_settings.cache_clear()

        settings = get_settings()

        self.assertEqual(
            settings,
            Settings(
                app_name="Agent Memory Runtime",
                environment="development",
                debug=False,
                api_prefix="/v1",
                api_port=8080,
                postgres_dsn="postgresql://postgres:postgres@localhost:5432/memory_runtime",
                redis_url="redis://localhost:6379/0",
            ),
        )

    def test_settings_from_environment(self) -> None:
        os.environ["MEMORY_RUNTIME_APP_NAME"] = "Custom Runtime"
        os.environ["MEMORY_RUNTIME_ENV"] = "test"
        os.environ["MEMORY_RUNTIME_DEBUG"] = "true"
        os.environ["MEMORY_RUNTIME_API_PREFIX"] = "/api"
        os.environ["MEMORY_RUNTIME_API_PORT"] = "9090"
        os.environ["MEMORY_RUNTIME_POSTGRES_DSN"] = "postgresql://db/test"
        os.environ["MEMORY_RUNTIME_REDIS_URL"] = "redis://cache/1"
        get_settings.cache_clear()

        settings = get_settings()

        self.assertEqual(settings.app_name, "Custom Runtime")
        self.assertEqual(settings.environment, "test")
        self.assertTrue(settings.debug)
        self.assertEqual(settings.api_prefix, "/api")
        self.assertEqual(settings.api_port, 9090)
        self.assertEqual(settings.postgres_dsn, "postgresql://db/test")
        self.assertEqual(settings.redis_url, "redis://cache/1")
