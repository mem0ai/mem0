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


def _load_yaml_config_path() -> Dict[str, Any]:
    """Load a YAML config file from the path given by ``MEM0_CONFIG_PATH``.

    Returns the parsed dict on success, an empty dict when the env var is unset,
    or an empty dict (after logging a clear error) when the file is missing or
    contains invalid YAML — matching mem0's existing fail-soft error style.
    """
    # Fail-soft on all errors (missing file, invalid YAML, non-mapping top-level) — matches
    # mem0's existing override-loading style in `_load_overrides`. An operator who misconfigures
    # MEM0_CONFIG_PATH will see ERROR logs on startup but the server will still boot on bare
    # defaults. Trade-off accepted: failing fast would prevent silent-wrong-config in K8s, but
    # fail-soft consistency with the surrounding code is preferred. Revisit if a prod incident
    # surfaces from a misconfigured ConfigMap mount.
    config_path = os.environ.get("MEM0_CONFIG_PATH", "").strip()
    if not config_path:
        return {}

    try:
        import yaml  # imported lazily — only needed when env var is set
    except ImportError:
        logging.error(
            "MEM0_CONFIG_PATH is set to %r but 'pyyaml' is not installed. "
            "Add pyyaml to server/requirements.txt and rebuild the image. "
            "Falling back to default configuration.",
            config_path,
        )
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except FileNotFoundError:
        logging.error(
            "MEM0_CONFIG_PATH is set to %r but the file does not exist. "
            "Falling back to default configuration.",
            config_path,
            exc_info=True,
        )
        return {}
    except yaml.YAMLError as exc:
        logging.error(
            "MEM0_CONFIG_PATH is set to %r but the file contains invalid YAML: %s. "
            "Falling back to default configuration.",
            config_path,
            exc,
            exc_info=True,
        )
        return {}

    if not isinstance(data, dict):
        logging.error(
            "MEM0_CONFIG_PATH is set to %r but the file does not contain a YAML mapping at the top level. "
            "Falling back to default configuration.",
            config_path,
        )
        return {}

    logging.info("Loaded mem0 config from MEM0_CONFIG_PATH=%r", config_path)
    return data


def initialize_state(default_config: Dict[str, Any]) -> None:
    global _current_config, _memory_instance
    with _state_lock:
        _current_config = deepcopy(default_config)
        yaml_overrides = _load_yaml_config_path()
        if yaml_overrides:
            _current_config = _merge_config(_current_config, yaml_overrides)
        overrides = _load_overrides()
        if overrides:
            _current_config = _merge_config(_current_config, overrides)
        _memory_instance = Memory.from_config(_current_config)


def update_config(updates: Dict[str, Any]) -> Dict[str, Any]:
    global _current_config, _memory_instance
    with _state_lock:
        next_config = _merge_config(_current_config, updates)
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
