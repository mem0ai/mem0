import json
import logging
import threading
from contextlib import contextmanager
from copy import deepcopy
from typing import Any, Callable, Dict, Iterable, Iterator

from mem0 import Memory
from mem0.configs.base import MemoryConfig
from mem0.vector_stores.base import VectorStoreConfigurationError
from pydantic import ValidationError as PydanticValidationError

_state_lock = threading.RLock()
_current_config: Dict[str, Any] = {}
_memory_instance: Memory | None = None
_session_factory: Callable | None = None
_locked_components: set[str] = set()
_active_leases: Dict[int, int] = {}
_retired_instances: Dict[int, Memory] = {}

_PROVIDER_COMPONENTS = {"vector_store", "llm", "embedder", "reranker"}


def set_session_factory(factory: Callable) -> None:
    global _session_factory
    _session_factory = factory


def _load_overrides() -> Dict[str, Any]:
    try:
        if _session_factory is None:
            return {}
        from models import Settings

        session = _session_factory()
        try:
            row = session.get(Settings, "config_overrides")
            if row is None:
                return {}
            overrides = json.loads(row.value)
            if not isinstance(overrides, dict):
                logging.warning("Ignoring malformed persisted config overrides: expected a JSON object")
                return {}
            return overrides
        finally:
            session.close()
    except Exception as exc:
        logging.warning("Failed to load config overrides from database (%s)", type(exc).__name__)
        return {}


def _merge_and_save_overrides(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Atomically merge persisted overrides under a cross-process Postgres lock."""
    if _session_factory is None:
        return deepcopy(updates)
    from models import Settings
    from sqlalchemy import select, text

    session = _session_factory()
    try:
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": "mem0.config_overrides"},
        )
        row = session.execute(
            select(Settings).where(Settings.key == "config_overrides").with_for_update()
        ).scalar_one_or_none()
        current = {}
        if row is not None:
            current = json.loads(row.value)
            if not isinstance(current, dict):
                raise RuntimeError("Persisted configuration overrides must be a JSON object.")

        merged = _merge_config(_without_locked_components(current), updates)
        serialized = json.dumps(merged)
        if row is None:
            session.add(Settings(key="config_overrides", value=serialized))
        else:
            row.value = serialized
        session.commit()
        return merged
    except Exception as exc:
        if hasattr(session, "rollback"):
            session.rollback()
        logging.warning("Failed to persist config overrides to database (%s)", type(exc).__name__)
        raise RuntimeError("Failed to persist Mem0 configuration.") from exc
    finally:
        session.close()


def _merge_config(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)

    for key, value in deepcopy(updates).items():
        if (
            key in _PROVIDER_COMPONENTS
            and isinstance(value, dict)
            and isinstance(merged.get(key), dict)
            and value.get("provider") is not None
            and value.get("provider") != merged[key].get("provider")
        ):
            merged[key] = value
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_config(merged[key], value)
        else:
            merged[key] = value

    return merged


def _without_locked_components(config: Dict[str, Any]) -> Dict[str, Any]:
    return {key: deepcopy(value) for key, value in config.items() if key not in _locked_components}


def _validated_config(config: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from vector_store_config import sanitized_validation_error_message, validate_server_config
    except ModuleNotFoundError:
        from server.vector_store_config import sanitized_validation_error_message, validate_server_config

    candidate = deepcopy(config)
    validate_server_config(candidate)
    try:
        model = MemoryConfig(**candidate)
    except PydanticValidationError as exc:
        raise ValueError(sanitized_validation_error_message(exc)) from None
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="python")
    if isinstance(model, dict):
        return deepcopy(model)
    return candidate


def _active_config(instance: Memory, fallback: Dict[str, Any]) -> Dict[str, Any]:
    config = getattr(instance, "config", None)
    if hasattr(config, "model_dump"):
        dumped = config.model_dump(mode="python")
        if isinstance(dumped, dict):
            return dumped
    return deepcopy(fallback)


def _close_memory_instance(instance: Memory | None) -> None:
    if instance is None:
        return

    resources = [
        getattr(getattr(instance, "vector_store", None), "client", None),
        getattr(getattr(instance, "_entity_store", None), "client", None),
        getattr(getattr(instance, "embedding_model", None), "client", None),
        getattr(getattr(instance, "llm", None), "client", None),
        getattr(instance, "db", None),
    ]
    closed_ids: set[int] = set()
    for resource in resources:
        if resource is None or id(resource) in closed_ids or not hasattr(resource, "close"):
            continue
        closed_ids.add(id(resource))
        try:
            resource.close()
        except Exception as exc:
            logging.warning("Failed to close a previous Mem0 runtime resource (%s)", type(exc).__name__)


def _retire_memory_instance(instance: Memory | None) -> None:
    if instance is None:
        return
    instance_id = id(instance)
    if _active_leases.get(instance_id, 0):
        _retired_instances[instance_id] = instance
        return
    _close_memory_instance(instance)


def initialize_state(default_config: Dict[str, Any], locked_components: Iterable[str] = ()) -> None:
    global _current_config, _memory_instance, _locked_components
    with _state_lock:
        _locked_components = set(locked_components)
        next_config = _validated_config(default_config)
        overrides = _load_overrides()
        if overrides:
            merged_config = _merge_config(default_config, _without_locked_components(overrides))
            try:
                next_config = _validated_config(merged_config)
            except Exception as exc:
                logging.warning("Ignoring invalid persisted config overrides (%s)", type(exc).__name__)
        try:
            next_instance = Memory.from_config(next_config)
        except VectorStoreConfigurationError:
            raise
        except Exception:
            raise RuntimeError("Failed to initialize Mem0 from the startup configuration.") from None
        next_config = _active_config(next_instance, next_config)
        previous_instance = _memory_instance
        _current_config = next_config
        _memory_instance = next_instance
        if previous_instance is not next_instance:
            _retire_memory_instance(previous_instance)


def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    global _current_config, _memory_instance
    with _state_lock:
        locked_updates = sorted(set(updates) & _locked_components)
        if locked_updates:
            joined = ", ".join(locked_updates)
            raise ValueError(f"Configuration component(s) managed by environment variables cannot be changed: {joined}")

        next_config = _validated_config(_merge_config(_current_config, updates))
        try:
            next_instance = Memory.from_config(next_config)
        except VectorStoreConfigurationError:
            raise
        except Exception as exc:
            raise RuntimeError("Failed to initialize the candidate Mem0 configuration.") from exc
        next_config = _active_config(next_instance, next_config)
        try:
            _merge_and_save_overrides(updates)
        except Exception:
            _close_memory_instance(next_instance)
            raise

        previous_instance = _memory_instance
        _current_config = next_config
        _memory_instance = next_instance
        if previous_instance is not next_instance:
            _retire_memory_instance(previous_instance)
        return deepcopy(_current_config)


def get_current_config() -> Dict[str, Any]:
    with _state_lock:
        return deepcopy(_current_config)


def get_memory_instance() -> Memory:
    with _state_lock:
        if _memory_instance is None:
            raise RuntimeError("Mem0 runtime has not been initialized.")
        return _memory_instance


@contextmanager
def memory_instance_lease() -> Iterator[Memory]:
    """Keep a runtime alive until the request using it has completed."""
    with _state_lock:
        if _memory_instance is None:
            raise RuntimeError("Mem0 runtime has not been initialized.")
        instance = _memory_instance
        instance_id = id(instance)
        _active_leases[instance_id] = _active_leases.get(instance_id, 0) + 1

    try:
        yield instance
    finally:
        close_instance = None
        with _state_lock:
            remaining = _active_leases.get(instance_id, 1) - 1
            if remaining:
                _active_leases[instance_id] = remaining
            else:
                _active_leases.pop(instance_id, None)
                close_instance = _retired_instances.pop(instance_id, None)
        if close_instance is not None:
            _close_memory_instance(close_instance)


def get_locked_components() -> set[str]:
    with _state_lock:
        return set(_locked_components)
