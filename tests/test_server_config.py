import json
import sys
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError as PydanticValidationError

from mem0.configs.base import MemoryConfig
from server import server_state
from server.errors import upstream_error
from server.vector_store_config import (
    build_vector_store_config,
    sanitized_validation_error_message,
    validate_server_config,
)


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
    "config",
    [
        {"path": "./qdrant-data", "api_key": "secret"},
        {"path": "./qdrant-data", "https": False},
        {"url": "https://qdrant", "host": "qdrant", "port": 6333},
    ],
)
def test_qdrant_modes_are_mutually_exclusive(config):
    with pytest.raises(RuntimeError):
        build_vector_store_config(
            {
                "VECTOR_STORE_PROVIDER": "qdrant",
                "VECTOR_STORE_CONFIG": json.dumps(config),
            }
        )


def test_server_validator_rejects_runtime_qdrant_without_endpoint():
    with pytest.raises(ValueError, match="requires a non-empty url"):
        validate_server_config({"vector_store": {"provider": "qdrant", "config": {}}})


def test_validation_error_message_omits_configuration_secrets():
    secret = "S3CR3T-short-sentinel"
    with pytest.raises(PydanticValidationError) as exc_info:
        MemoryConfig(
            vector_store={
                "provider": "qdrant",
                "config": {"url": "https://qdrant", "api_key": secret, "unsupported": True},
            }
        )

    message = sanitized_validation_error_message(exc_info.value)
    assert "unsupported" in message
    assert secret not in message


def test_server_validation_exception_omits_configuration_secrets():
    secret = "S3CR3T-startup-sentinel"
    with pytest.raises(ValueError) as exc_info:
        server_state._validated_config(
            {
                "vector_store": {
                    "provider": "qdrant",
                    "config": {"url": "https://qdrant", "api_key": secret, "unsupported": True},
                }
            }
        )

    assert secret not in str(exc_info.value)


def test_upstream_error_logging_omits_exception_text(caplog):
    secret = "S3CR3T-provider-sentinel"
    with caplog.at_level("ERROR"):
        try:
            raise RuntimeError(f"provider echoed {secret}")
        except RuntimeError:
            error = upstream_error()

    assert error.status_code == 502
    assert secret not in error.detail
    assert secret not in caplog.text


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
    monkeypatch.setattr(server_state, "_active_leases", {})
    monkeypatch.setattr(server_state, "_retired_instances", {})
    monkeypatch.setattr(server_state, "_load_overrides", lambda **kwargs: {})
    monkeypatch.setattr(server_state, "_merge_and_save_overrides", lambda updates: deepcopy(updates))
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


def test_runtime_qdrant_without_endpoint_is_rejected_before_construction(monkeypatch):
    current = {"vector_store": {"provider": "pgvector", "config": {"host": "postgres"}}}
    current_instance = MagicMock()
    _prepare_state(monkeypatch, current, current_instance)
    from_config = MagicMock()
    monkeypatch.setattr(server_state.Memory, "from_config", from_config)

    with pytest.raises(ValueError, match="requires a non-empty url"):
        server_state.update_config({"vector_store": {"provider": "qdrant", "config": {}}})

    from_config.assert_not_called()
    assert server_state.get_memory_instance() is current_instance


def test_invalid_persisted_qdrant_override_is_ignored_without_logging_secret(monkeypatch, caplog):
    default = {"vector_store": {"provider": "pgvector", "config": {"host": "postgres"}}}
    monkeypatch.setattr(
        server_state,
        "_load_overrides",
        lambda: {"vector_store": {"provider": "qdrant", "config": {"api_key": "S3CR3T"}}},
    )
    monkeypatch.setattr(server_state, "MemoryConfig", lambda **kwargs: kwargs)
    created = MagicMock()
    from_config = MagicMock(return_value=created)
    monkeypatch.setattr(server_state.Memory, "from_config", from_config)
    monkeypatch.setattr(server_state, "_memory_instance", None)

    server_state.initialize_state(default)

    assert from_config.call_args.args[0]["vector_store"]["provider"] == "pgvector"
    assert "S3CR3T" not in caplog.text


def test_failed_persistence_keeps_previous_runtime(monkeypatch):
    current = {"llm": {"provider": "openai", "config": {"model": "old"}}}
    current_instance = MagicMock()
    candidate = MagicMock()
    _prepare_state(monkeypatch, current, current_instance)
    monkeypatch.setattr(server_state.Memory, "from_config", MagicMock(return_value=candidate))
    monkeypatch.setattr(
        server_state,
        "_merge_and_save_overrides",
        MagicMock(side_effect=RuntimeError("persistence failed")),
    )

    with pytest.raises(RuntimeError, match="persistence failed"):
        server_state.update_config({"llm": {"config": {"model": "new"}}})

    assert server_state.get_current_config() == current
    assert server_state.get_memory_instance() is current_instance
    candidate.vector_store.client.close.assert_called_once()


def test_failed_candidate_construction_keeps_previous_runtime_and_sanitizes_error(monkeypatch):
    current = {"llm": {"provider": "openai", "config": {"model": "old"}}}
    current_instance = MagicMock()
    _prepare_state(monkeypatch, current, current_instance)
    monkeypatch.setattr(
        server_state.Memory,
        "from_config",
        MagicMock(side_effect=ValueError("provider echoed api key S3CR3T")),
    )

    with pytest.raises(RuntimeError, match="candidate Mem0 configuration") as exc_info:
        server_state.update_config({"llm": {"config": {"model": "new"}}})

    assert "S3CR3T" not in str(exc_info.value)
    assert server_state.get_current_config() == current
    assert server_state.get_memory_instance() is current_instance


def test_successful_update_persists_before_swapping(monkeypatch):
    current = {"llm": {"provider": "openai", "config": {"model": "old", "temperature": 0.2}}}
    current_instance = MagicMock()
    candidate = MagicMock()
    _prepare_state(monkeypatch, current, current_instance)
    monkeypatch.setattr(server_state.Memory, "from_config", MagicMock(return_value=candidate))
    save = MagicMock()
    monkeypatch.setattr(server_state, "_merge_and_save_overrides", save)

    result = server_state.update_config({"llm": {"config": {"model": "new"}}})

    assert result["llm"]["config"] == {"model": "new", "temperature": 0.2}
    save.assert_called_once_with({"llm": {"config": {"model": "new"}}})
    assert server_state.get_memory_instance() is candidate
    current_instance.vector_store.client.close.assert_called_once()


def test_successful_update_retires_old_runtime_after_active_lease(monkeypatch):
    current = {"llm": {"provider": "openai", "config": {"model": "old"}}}
    current_instance = MagicMock()
    candidate = MagicMock()
    _prepare_state(monkeypatch, current, current_instance)
    monkeypatch.setattr(server_state.Memory, "from_config", MagicMock(return_value=candidate))

    with server_state.memory_instance_lease() as leased:
        assert leased is current_instance
        server_state.update_config({"llm": {"config": {"model": "new"}}})
        current_instance.vector_store.client.close.assert_not_called()

    current_instance.vector_store.client.close.assert_called_once()


def test_persisted_updates_use_cross_process_lock_and_merge(monkeypatch):
    class FakeSelect:
        def where(self, condition):
            return self

        def with_for_update(self):
            return self

    class FakeSettings:
        key = "key"

        def __init__(self, key, value):
            self.key = key
            self.value = value

    row = SimpleNamespace(
        value=json.dumps({"llm": {"provider": "openai", "config": {"model": "old", "temperature": 0.2}}})
    )
    lock_result = MagicMock()
    row_result = MagicMock()
    row_result.scalar_one_or_none.return_value = row
    session = MagicMock()
    session.execute.side_effect = [lock_result, row_result]
    monkeypatch.setattr(server_state, "_session_factory", lambda: session)
    monkeypatch.setitem(sys.modules, "models", SimpleNamespace(Settings=FakeSettings))

    import sqlalchemy

    monkeypatch.setattr(sqlalchemy, "select", lambda model: FakeSelect())
    monkeypatch.setattr(sqlalchemy, "text", lambda statement: statement)

    merged = server_state._merge_and_save_overrides({"llm": {"config": {"model": "new"}}})

    assert merged["llm"]["config"] == {"model": "new", "temperature": 0.2}
    assert json.loads(row.value) == merged
    assert "pg_advisory_xact_lock" in session.execute.call_args_list[0].args[0]
    session.commit.assert_called_once()
