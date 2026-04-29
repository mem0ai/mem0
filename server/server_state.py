from __future__ import annotations

import json
import logging
import os
import threading
from copy import deepcopy
from typing import Any, Callable, Dict

from mem0 import Memory

_state_lock = threading.RLock()
_current_config: Dict[str, Any] = {}
_memory_instance: Memory | None = None
_session_factory: Callable | None = None

PROVIDER_API_KEY_ENV_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "openai": "OPENAI_API_KEY",
}


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
            return json.loads(row.value)
        finally:
            session.close()
    except Exception:
        return {}


def _save_overrides(overrides: Dict[str, Any]) -> None:
    try:
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
        finally:
            session.close()
    except Exception:
        logging.warning("Failed to persist config overrides to database", exc_info=True)


def _merge_config(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)

    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_config(merged[key], value)
        else:
            merged[key] = value

    return merged


def _clear_api_keys_for_provider_changes(
    base: Dict[str, Any], updates: Dict[str, Any], *, persisted_overrides: bool = False
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    cleaned_base = deepcopy(base)
    cleaned_updates = deepcopy(updates)

    for section_name in ("llm", "embedder"):
        section_update = cleaned_updates.get(section_name)
        section_base = cleaned_base.get(section_name)
        if not isinstance(section_update, dict) or not isinstance(section_base, dict):
            continue
        if section_update.get("provider") == section_base.get("provider"):
            continue

        base_config = section_base.get("config")
        old_api_key = base_config.get("api_key") if isinstance(base_config, dict) else None
        if isinstance(base_config, dict):
            base_config.pop("api_key", None)

        update_config = section_update.get("config")
        if isinstance(update_config, dict):
            if persisted_overrides or update_config.get("api_key") == old_api_key:
                update_config.pop("api_key", None)

    return cleaned_base, cleaned_updates


def _apply_env_api_keys(config: Dict[str, Any]) -> Dict[str, Any]:
    effective_config = deepcopy(config)

    for section_name in ("llm", "embedder"):
        section = effective_config.get(section_name)
        if not isinstance(section, dict):
            continue

        provider = section.get("provider")
        env_var = PROVIDER_API_KEY_ENV_VARS.get(provider)
        if not env_var:
            continue

        api_key = os.environ.get(env_var)
        if not api_key:
            continue

        section_config = section.get("config")
        if not isinstance(section_config, dict):
            section_config = {}
            section["config"] = section_config
        section_config["api_key"] = api_key

    return effective_config


def initialize_state(default_config: Dict[str, Any]) -> None:
    global _current_config, _memory_instance
    with _state_lock:
        _current_config = deepcopy(default_config)
        overrides = _load_overrides()
        if overrides:
            _current_config, overrides = _clear_api_keys_for_provider_changes(
                _current_config, overrides, persisted_overrides=True
            )
            _current_config = _merge_config(_current_config, overrides)
        _current_config = _apply_env_api_keys(_current_config)
        _memory_instance = Memory.from_config(_current_config)


def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    global _current_config, _memory_instance
    with _state_lock:
        base_config, cleaned_updates = _clear_api_keys_for_provider_changes(_current_config, updates)
        next_config = _apply_env_api_keys(_merge_config(base_config, cleaned_updates))
        _current_config = next_config
        _memory_instance = Memory.from_config(next_config)
        overrides = _load_overrides()
        overrides = _merge_config(overrides, updates)
        _save_overrides(overrides)
        return deepcopy(_current_config)


def get_current_config() -> Dict[str, Any]:
    with _state_lock:
        return deepcopy(_current_config)


def get_memory_instance() -> Memory:
    with _state_lock:
        if _memory_instance is None:
            raise RuntimeError("Mem0 runtime has not been initialized.")
        return _memory_instance
