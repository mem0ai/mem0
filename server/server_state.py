import json
import logging
import threading
from copy import deepcopy
from typing import Any, Callable, Dict, Iterable

from mem0 import Memory
from mem0.configs.base import MemoryConfig

_state_lock = threading.RLock()
_current_config: Dict[str, Any] = {}
_memory_instance: Memory | None = None
_session_factory: Callable | None = None
_locked_components: set[str] = set()

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


def _save_overrides(overrides: Dict[str, Any]) -> None:
    if _session_factory is None:
        return
    from models import Settings
    from sqlalchemy.dialects.postgresql import insert

    session = _session_factory()
    try:
        serialized = json.dumps(overrides)
        stmt = (
            insert(Settings)
            .values(key="config_overrides", value=serialized)
            .on_conflict_do_update(
                index_elements=[Settings.key],
                set_={"value": serialized},
            )
        )
        session.execute(stmt)
        session.commit()
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


def _close_memory_instance(instance: Memory | None) -> None:
    if instance is None:
        return
    try:
        vector_client = getattr(getattr(instance, "vector_store", None), "client", None)
        if vector_client is not None and hasattr(vector_client, "close"):
            vector_client.close()
        history_db = getattr(instance, "db", None)
        if history_db is not None and hasattr(history_db, "close"):
            history_db.close()
    except Exception as exc:
        logging.warning("Failed to close the previous Mem0 runtime (%s)", type(exc).__name__)


def initialize_state(default_config: Dict[str, Any], locked_components: Iterable[str] = ()) -> None:
    global _current_config, _memory_instance, _locked_components
    with _state_lock:
        _locked_components = set(locked_components)
        next_config = deepcopy(default_config)
        overrides = _load_overrides()
        if overrides:
            next_config = _merge_config(next_config, _without_locked_components(overrides))
        MemoryConfig(**deepcopy(next_config))
        next_instance = Memory.from_config(next_config)
        previous_instance = _memory_instance
        _current_config = next_config
        _memory_instance = next_instance
        if previous_instance is not next_instance:
            _close_memory_instance(previous_instance)


def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    global _current_config, _memory_instance
    with _state_lock:
        locked_updates = sorted(set(updates) & _locked_components)
        if locked_updates:
            joined = ", ".join(locked_updates)
            raise ValueError(f"Configuration component(s) managed by environment variables cannot be changed: {joined}")

        next_config = _merge_config(_current_config, updates)
        MemoryConfig(**deepcopy(next_config))
        next_instance = Memory.from_config(next_config)
        overrides = _load_overrides()
        next_overrides = _merge_config(_without_locked_components(overrides), updates)
        try:
            _save_overrides(next_overrides)
        except Exception:
            _close_memory_instance(next_instance)
            raise

        previous_instance = _memory_instance
        _current_config = next_config
        _memory_instance = next_instance
        if previous_instance is not next_instance:
            _close_memory_instance(previous_instance)
        return deepcopy(_current_config)


def get_current_config() -> Dict[str, Any]:
    with _state_lock:
        return deepcopy(_current_config)


def get_memory_instance() -> Memory:
    with _state_lock:
        if _memory_instance is None:
            raise RuntimeError("Mem0 runtime has not been initialized.")
        return _memory_instance


def get_locked_components() -> set[str]:
    with _state_lock:
        return set(_locked_components)
