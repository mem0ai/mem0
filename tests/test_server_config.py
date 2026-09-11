"""Tests for server configuration: VECTOR_STORE_CONFIG parsing and provider-switch config clearing.

Covers:
- VECTOR_STORE_CONFIG env var parsing (valid JSON, invalid JSON, missing)
- COLLECTION_NAME env var (with backward-compat POSTGRES_COLLECTION_NAME fallback)
- Fallback warning when provider != pgvector and no VECTOR_STORE_CONFIG
- update_config clearing old provider config on provider switch (no mutation of live state)
- _list_all_memories handling of tuple results from vector stores like Qdrant
"""

import importlib
import os
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")


# ---------------------------------------------------------------------------
# Helpers: make server importable both from repo root (tests/) and inside
# the Docker container (/app/) where the files live at the top level.
# ---------------------------------------------------------------------------

def _import_server_main():
    """Import server main module, handling both repo and container layouts."""
    try:
        import server.main as mod
        return mod
    except ModuleNotFoundError:
        import main as mod
        return mod


def _import_server_state():
    """Import server_state module, handling both repo and container layouts."""
    try:
        import server.server_state as mod
        return mod
    except ModuleNotFoundError:
        import server_state as mod
        return mod


def _reload_main_with_env(env_overrides):
    """Reload server main with the given env vars and return the module."""
    base_env = {
        "OPENAI_API_KEY": "fake-key",
        "ADMIN_API_KEY": "",
        "POSTGRES_PASSWORD": "test",
    }
    base_env.update(env_overrides)
    with patch.dict(os.environ, base_env, clear=False):
        with patch("mem0.Memory.from_config", return_value=MagicMock()):
            mod = _import_server_main()
            importlib.reload(mod)
            return mod


# ===========================================================================
# VECTOR_STORE_CONFIG env var parsing
# ===========================================================================


class TestVectorStoreConfigEnvVar:
    """Verify that the VECTOR_STORE_CONFIG env var is parsed and merged correctly."""

    def test_qdrant_config_parsed(self):
        """Valid JSON in VECTOR_STORE_CONFIG should be merged into vector_store_config."""
        mod = _reload_main_with_env({
            "VECTOR_STORE_PROVIDER": "qdrant",
            "VECTOR_STORE_CONFIG": '{"host": "qdrant", "port": 6333}',
        })
        vs = mod.DEFAULT_CONFIG["vector_store"]
        assert vs["provider"] == "qdrant"
        assert vs["config"]["host"] == "qdrant"
        assert vs["config"]["port"] == 6333

    def test_invalid_json_falls_back(self):
        """Malformed JSON should log an error but not crash; config stays minimal."""
        mod = _reload_main_with_env({
            "VECTOR_STORE_PROVIDER": "qdrant",
            "VECTOR_STORE_CONFIG": "NOT_JSON{{{",
        })
        vs = mod.DEFAULT_CONFIG["vector_store"]
        assert vs["provider"] == "qdrant"
        # Only collection_name should remain since JSON parsing failed
        assert "host" not in vs["config"]

    def test_pgvector_fallback_uses_postgres_env(self):
        """When provider is pgvector and no VECTOR_STORE_CONFIG, postgres env vars are used."""
        mod = _reload_main_with_env({
            "VECTOR_STORE_PROVIDER": "pgvector",
            "POSTGRES_HOST": "myhost",
            "POSTGRES_PORT": "5433",
            "POSTGRES_DB": "mydb",
            "POSTGRES_USER": "myuser",
            "POSTGRES_PASSWORD": "mypass",
        })
        vs = mod.DEFAULT_CONFIG["vector_store"]
        assert vs["provider"] == "pgvector"
        assert vs["config"]["host"] == "myhost"
        assert vs["config"]["port"] == 5433
        assert vs["config"]["dbname"] == "mydb"

    def test_non_pgvector_without_config_warns(self):
        """Non-pgvector provider with no VECTOR_STORE_CONFIG should trigger a warning."""
        with patch("logging.warning") as mock_warn:
            _reload_main_with_env({
                "VECTOR_STORE_PROVIDER": "qdrant",
                # No VECTOR_STORE_CONFIG
            })
            assert mock_warn.called
            call_args = mock_warn.call_args
            assert "VECTOR_STORE_CONFIG is not provided" in call_args[0][0]


# ===========================================================================
# COLLECTION_NAME env var with backward-compat fallback
# ===========================================================================


class TestCollectionNameEnvVar:
    """Verify COLLECTION_NAME reads from the new name, falls back to POSTGRES_COLLECTION_NAME."""

    def test_collection_name_env(self):
        mod = _reload_main_with_env({"COLLECTION_NAME": "my_memories"})
        assert mod.COLLECTION_NAME == "my_memories"

    def test_postgres_collection_name_fallback(self):
        mod = _reload_main_with_env({"POSTGRES_COLLECTION_NAME": "legacy_memories"})
        assert mod.COLLECTION_NAME == "legacy_memories"

    def test_default_collection_name(self):
        mod = _reload_main_with_env({})
        assert mod.COLLECTION_NAME == "memories"


# ===========================================================================
# update_config: provider-switch config clearing
# ===========================================================================


class TestUpdateConfigProviderSwitch:
    """Verify update_config correctly clears old provider config on switch.

    These tests call update_config() directly with _load_overrides, _save_overrides,
    and Memory.from_config mocked, exercising the full lock → deepcopy → clear →
    merge → reinit → persist pipeline.
    """

    def _setup_state(self, initial_config, stored_overrides=None):
        """Initialize server_state with a known config and return (module, mock_memory_cls).

        Args:
            initial_config: The starting _current_config.
            stored_overrides: What _load_overrides should return (simulates DB).

        Returns:
            (state_module, mock_from_config) — call state_module.update_config(...)
            then inspect mock_from_config.call_args to verify the config passed.
        """
        state_mod = _import_server_state()
        importlib.reload(state_mod)

        saved_overrides = {}

        def fake_save(overrides):
            saved_overrides.update(overrides)

        mock_memory = MagicMock()

        with patch.object(state_mod, "_load_overrides", return_value=stored_overrides or {}):
            with patch.object(state_mod, "_save_overrides", side_effect=fake_save) as mock_save:
                with patch("mem0.Memory.from_config", return_value=mock_memory) as mock_from_config:
                    state_mod.initialize_state(initial_config)
                    yield state_mod, mock_from_config, mock_save, saved_overrides

    def test_switch_clears_old_vector_store_config(self):
        """Switching vector_store provider via update_config should drop old config keys."""
        initial = {
            "version": "v1.1",
            "vector_store": {
                "provider": "pgvector",
                "config": {
                    "host": "postgres", "port": 5432,
                    "dbname": "mem0", "user": "postgres", "password": "secret",
                    "collection_name": "memories",
                },
            },
            "llm": {"provider": "openai", "config": {"api_key": "k"}},
        }
        updates = {
            "vector_store": {
                "provider": "qdrant",
                "config": {"host": "qdrant", "port": 6333},
            },
        }

        gen = self._setup_state(initial)
        state_mod, mock_from_config, mock_save, _ = next(gen)

        result = state_mod.update_config(updates)

        # Old pgvector keys must NOT leak
        vs_config = result["vector_store"]["config"]
        assert "dbname" not in vs_config
        assert "user" not in vs_config
        assert "password" not in vs_config
        # New qdrant keys must be present
        assert vs_config["host"] == "qdrant"
        assert vs_config["port"] == 6333
        assert result["vector_store"]["provider"] == "qdrant"

        # Memory.from_config must have been called with the clean config
        reinit_config = mock_from_config.call_args_list[-1][0][0]
        assert "dbname" not in reinit_config["vector_store"]["config"]
        assert reinit_config["vector_store"]["provider"] == "qdrant"

    def test_switch_clears_stored_overrides(self):
        """When switching providers, stored overrides config must also be cleared."""
        initial = {
            "version": "v1.1",
            "vector_store": {
                "provider": "pgvector",
                "config": {"host": "postgres", "dbname": "mem0"},
            },
        }
        stored = {
            "vector_store": {
                "provider": "pgvector",
                "config": {"host": "custom-pg", "dbname": "custom_db", "password": "pw"},
            },
        }
        updates = {
            "vector_store": {
                "provider": "qdrant",
                "config": {"host": "qdrant", "port": 6333},
            },
        }

        gen = self._setup_state(initial, stored_overrides=stored)
        state_mod, _, mock_save, saved = next(gen)

        state_mod.update_config(updates)

        # _save_overrides must have been called
        assert mock_save.called
        # Saved overrides must NOT contain old pgvector keys
        saved_vs = saved.get("vector_store", {}).get("config", {})
        assert "dbname" not in saved_vs
        assert "password" not in saved_vs
        # New keys should be present in saved overrides
        assert saved_vs.get("host") == "qdrant"

    def test_same_provider_preserves_config(self):
        """Updating with the same provider should NOT clear the config."""
        initial = {
            "version": "v1.1",
            "vector_store": {
                "provider": "qdrant",
                "config": {"host": "qdrant", "port": 6333, "collection_name": "memories"},
            },
        }
        updates = {
            "vector_store": {
                "provider": "qdrant",
                "config": {"port": 6334},
            },
        }

        gen = self._setup_state(initial)
        state_mod, _, _, _ = next(gen)

        result = state_mod.update_config(updates)

        # host should be preserved via deep merge (not cleared)
        assert result["vector_store"]["config"]["host"] == "qdrant"
        assert result["vector_store"]["config"]["port"] == 6334
        assert result["vector_store"]["config"]["collection_name"] == "memories"

    def test_no_mutation_of_live_config(self):
        """update_config must not mutate _current_config visible to get_current_config()
        until the new Memory instance is successfully created."""
        initial = {
            "version": "v1.1",
            "vector_store": {
                "provider": "pgvector",
                "config": {"host": "postgres", "dbname": "mem0"},
            },
        }

        gen = self._setup_state(initial)
        state_mod, _, _, _ = next(gen)

        # Snapshot before update
        before = state_mod.get_current_config()
        assert before["vector_store"]["config"]["host"] == "postgres"

        # Perform update
        state_mod.update_config({
            "vector_store": {
                "provider": "qdrant",
                "config": {"host": "qdrant", "port": 6333},
            },
        })

        # After update, get_current_config should reflect new state
        after = state_mod.get_current_config()
        assert after["vector_store"]["provider"] == "qdrant"
        assert "dbname" not in after["vector_store"]["config"]

    def test_llm_provider_switch_clears_config(self):
        """Switching LLM provider should also clear old LLM config keys."""
        initial = {
            "version": "v1.1",
            "vector_store": {"provider": "qdrant", "config": {"host": "qdrant"}},
            "llm": {
                "provider": "openai",
                "config": {"api_key": "sk-old", "model": "gpt-4", "temperature": 0.2},
            },
        }
        updates = {
            "llm": {
                "provider": "anthropic",
                "config": {"api_key": "***", "model": "claude-3"},
            },
        }

        gen = self._setup_state(initial)
        state_mod, _, _, _ = next(gen)

        result = state_mod.update_config(updates)

        # Old OpenAI-specific keys should be gone
        llm_config = result["llm"]["config"]
        assert llm_config.get("api_key") == "***"
        assert llm_config.get("model") == "claude-3"
        # temperature was openai-specific, should not leak
        assert "temperature" not in llm_config


# ===========================================================================
# _list_all_memories: tuple result handling
# ===========================================================================


class TestListAllMemoriesTupleHandling:
    """Verify _list_all_memories correctly handles both list and tuple results."""

    def _setup_main(self):
        """Reload server main with mocked Memory and return (module, mock_instance)."""
        mock_instance = MagicMock()
        with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key", "ADMIN_API_KEY": "", "AUTH_DISABLED": "true"}):
            with patch("mem0.Memory.from_config", return_value=mock_instance):
                mod = _import_server_main()
                importlib.reload(mod)
                return mod, mock_instance

    def test_list_result_works(self):
        """Standard list result from vector store should be handled."""
        mod, mock_mem = self._setup_main()
        mock_row = MagicMock()
        mock_row.id = "1"
        mock_row.payload = {"data": "test", "hash": "h1", "created_at": "2024-01-01", "updated_at": "2024-01-01"}
        mock_mem.vector_store.list.return_value = [mock_row]

        result = mod._list_all_memories()
        assert "results" in result
        assert len(result["results"]) == 1
        assert result["results"][0]["id"] == "1"

    def test_tuple_result_works(self):
        """Tuple result (as returned by Qdrant) should be handled without error."""
        mod, mock_mem = self._setup_main()
        mock_row = MagicMock()
        mock_row.id = "1"
        mock_row.payload = {"data": "test", "hash": "h1", "created_at": "2024-01-01", "updated_at": "2024-01-01"}
        records = [mock_row]
        # Qdrant returns (records, next_page_offset) as a tuple
        mock_mem.vector_store.list.return_value = (records, None)

        result = mod._list_all_memories()
        assert "results" in result
        assert len(result["results"]) == 1
        assert result["results"][0]["id"] == "1"

    def test_empty_result_works(self):
        """Empty result should return empty list."""
        mod, mock_mem = self._setup_main()
        mock_mem.vector_store.list.return_value = []

        result = mod._list_all_memories()
        assert result == {"results": []}

    def test_none_result_works(self):
        """None result should return empty list."""
        mod, mock_mem = self._setup_main()
        mock_mem.vector_store.list.return_value = None

        result = mod._list_all_memories()
        assert result == {"results": []}
