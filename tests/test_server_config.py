from copy import deepcopy
from unittest.mock import MagicMock

import pytest

from server import server_state
from server.vector_store_config import build_vector_store_config


def test_legacy_pgvector_config_when_generic_environment_is_absent():
    config, locked = build_vector_store_config(
        {
            "POSTGRES_HOST": "db",
            "POSTGRES_PORT": "5433",
            "POSTGRES_DB": "mem0",
            "POSTGRES_USER": "mem0",
            "POSTGRES_PASSWORD": "secret",
            "POSTGRES_COLLECTION_NAME": "legacy",
        }
    )

    assert locked == set()
    assert config == {
        "provider": "pgvector",
        "config": {
            "host": "db",
            "port": 5433,
            "dbname": "mem0",
            "user": "mem0",
            "password": "secret",
            "collection_name": "legacy",
        },
    }


def test_remote_qdrant_config_is_locked_and_prefers_json_collection():
    config, locked = build_vector_store_config(
        {
            "VECTOR_STORE_PROVIDER": "qdrant",
            "VECTOR_STORE_CONFIG": (
                '{"url":"https://qdrant.internal:6333","api_key":"secret",'
                '"collection_name":"from-json","embedding_model_dims":1024}'
            ),
            "COLLECTION_NAME": "from-generic",
            "POSTGRES_COLLECTION_NAME": "from-legacy",
        }
    )

    assert locked == {"vector_store"}
    assert config["provider"] == "qdrant"
    assert config["config"]["collection_name"] == "from-json"
    assert "path" not in config["config"]


def test_qdrant_host_port_and_explicit_local_modes(caplog):
    remote, _ = build_vector_store_config(
        {
            "VECTOR_STORE_PROVIDER": "qdrant",
            "VECTOR_STORE_CONFIG": '{"host":"qdrant","port":"6333"}',
        }
    )
    assert remote["config"]["port"] == 6333

    local, _ = build_vector_store_config(
        {
            "VECTOR_STORE_PROVIDER": "qdrant",
            "VECTOR_STORE_CONFIG": '{"path":"./qdrant-data"}',
        }
    )
    assert local["config"]["path"] == "./qdrant-data"
    assert "production" in caplog.text


@pytest.mark.parametrize(
    ("environ", "message"),
    [
        ({"VECTOR_STORE_CONFIG": "{}"}, "VECTOR_STORE_PROVIDER is required"),
        (
            {"VECTOR_STORE_PROVIDER": "qdrant"},
            "VECTOR_STORE_CONFIG is required",
        ),
        (
            {"VECTOR_STORE_PROVIDER": "qdrant", "VECTOR_STORE_CONFIG": "not-json"},
            "valid JSON object",
        ),
        (
            {"VECTOR_STORE_PROVIDER": "qdrant", "VECTOR_STORE_CONFIG": "[]"},
            "decode to a JSON object",
        ),
        (
            {"VECTOR_STORE_PROVIDER": "qdrant", "VECTOR_STORE_CONFIG": "{}"},
            "requires a non-empty url",
        ),
        (
            {
                "VECTOR_STORE_PROVIDER": "qdrant",
                "VECTOR_STORE_CONFIG": '{"host":"qdrant","port":0}',
            },
            "port between 1 and 65535",
        ),
        (
            {
                "VECTOR_STORE_PROVIDER": "qdrant",
                "VECTOR_STORE_CONFIG": '{"url":"https://qdrant","path":"./local"}',
            },
            "cannot be configured together",
        ),
    ],
)
def test_invalid_explicit_vector_store_configuration_fails(environ, message):
    with pytest.raises(RuntimeError, match=message) as exc_info:
        build_vector_store_config(environ)

    assert "api_key" not in str(exc_info.value)
    assert "secret" not in str(exc_info.value)


def test_merge_replaces_changed_provider_without_mutating_inputs():
    base = {"vector_store": {"provider": "pgvector", "config": {"password": "old", "port": 5432}}}
    update = {"vector_store": {"provider": "qdrant", "config": {"url": "https://qdrant"}}}
    base_before = deepcopy(base)
    update_before = deepcopy(update)

    merged = server_state._merge_config(base, update)

    assert merged == update
    assert base == base_before
    assert update == update_before


def test_merge_deep_merges_same_provider():
    base = {"llm": {"provider": "openai", "config": {"model": "old", "temperature": 0.2}}}
    update = {"llm": {"provider": "openai", "config": {"model": "new"}}}

    assert server_state._merge_config(base, update) == {
        "llm": {"provider": "openai", "config": {"model": "new", "temperature": 0.2}}
    }


def _prepare_state(monkeypatch, current_config, current_instance):
    monkeypatch.setattr(server_state, "_current_config", deepcopy(current_config))
    monkeypatch.setattr(server_state, "_memory_instance", current_instance)
    monkeypatch.setattr(server_state, "_locked_components", set())
    monkeypatch.setattr(server_state, "_load_overrides", lambda: {})
    monkeypatch.setattr(server_state, "MemoryConfig", lambda **kwargs: kwargs)


def test_environment_lock_ignores_persisted_vector_store(monkeypatch):
    default = {
        "vector_store": {"provider": "qdrant", "config": {"url": "https://qdrant"}},
        "llm": {"provider": "openai", "config": {"model": "base"}},
    }
    monkeypatch.setattr(
        server_state,
        "_load_overrides",
        lambda: {
            "vector_store": {"provider": "pgvector", "config": {"password": "stale"}},
            "llm": {"provider": "openai", "config": {"model": "persisted"}},
        },
    )
    monkeypatch.setattr(server_state, "MemoryConfig", lambda **kwargs: kwargs)
    created = MagicMock()
    from_config = MagicMock(return_value=created)
    monkeypatch.setattr(server_state.Memory, "from_config", from_config)
    monkeypatch.setattr(server_state, "_memory_instance", None)

    server_state.initialize_state(default, locked_components={"vector_store"})

    effective = from_config.call_args.args[0]
    assert effective["vector_store"]["provider"] == "qdrant"
    assert effective["llm"]["config"]["model"] == "persisted"


def test_locked_runtime_update_is_rejected_before_construction(monkeypatch):
    current = {"vector_store": {"provider": "qdrant", "config": {"url": "https://qdrant"}}}
    current_instance = MagicMock()
    _prepare_state(monkeypatch, current, current_instance)
    monkeypatch.setattr(server_state, "_locked_components", {"vector_store"})
    from_config = MagicMock()
    monkeypatch.setattr(server_state.Memory, "from_config", from_config)

    with pytest.raises(ValueError, match="managed by environment variables"):
        server_state.update_config({"vector_store": {"config": {"collection_name": "other"}}})

    from_config.assert_not_called()
    assert server_state.get_current_config() == current
    assert server_state.get_memory_instance() is current_instance


def test_failed_persistence_keeps_previous_runtime(monkeypatch):
    current = {"llm": {"provider": "openai", "config": {"model": "old"}}}
    current_instance = MagicMock()
    candidate = MagicMock()
    _prepare_state(monkeypatch, current, current_instance)
    monkeypatch.setattr(server_state.Memory, "from_config", MagicMock(return_value=candidate))
    monkeypatch.setattr(
        server_state,
        "_save_overrides",
        MagicMock(side_effect=RuntimeError("persistence failed")),
    )

    with pytest.raises(RuntimeError, match="persistence failed"):
        server_state.update_config({"llm": {"config": {"model": "new"}}})

    assert server_state.get_current_config() == current
    assert server_state.get_memory_instance() is current_instance
    candidate.vector_store.client.close.assert_called_once()


def test_successful_update_persists_before_swapping(monkeypatch):
    current = {"llm": {"provider": "openai", "config": {"model": "old", "temperature": 0.2}}}
    current_instance = MagicMock()
    candidate = MagicMock()
    _prepare_state(monkeypatch, current, current_instance)
    monkeypatch.setattr(server_state.Memory, "from_config", MagicMock(return_value=candidate))
    save = MagicMock()
    monkeypatch.setattr(server_state, "_save_overrides", save)

    result = server_state.update_config({"llm": {"config": {"model": "new"}}})

    assert result["llm"]["config"] == {"model": "new", "temperature": 0.2}
    save.assert_called_once_with({"llm": {"config": {"model": "new"}}})
    assert server_state.get_memory_instance() is candidate
    current_instance.vector_store.client.close.assert_called_once()
