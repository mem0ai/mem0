import json
import logging
from copy import deepcopy
from typing import Mapping, Type

from pydantic import ValidationError


def _collection_name(environ: Mapping[str, str]) -> str:
    return environ.get("COLLECTION_NAME") or environ.get("POSTGRES_COLLECTION_NAME") or "memories"


def _parse_json_object(raw_config: str) -> dict:
    try:
        parsed = json.loads(raw_config)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("VECTOR_STORE_CONFIG must be a valid JSON object.") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("VECTOR_STORE_CONFIG must decode to a JSON object.")
    return parsed


def _validate_qdrant_config(config: dict, error_type: Type[Exception] = RuntimeError) -> None:
    url = config.get("url")
    host = config.get("host")
    port = config.get("port")
    path = config.get("path")

    has_url = isinstance(url, str) and bool(url.strip())
    has_host = isinstance(host, str) and bool(host.strip())
    has_path = isinstance(path, str) and bool(path.strip())
    has_remote = has_url or has_host

    if has_host:
        if isinstance(port, str) and port.isdigit():
            port = int(port)
            config["port"] = port
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            raise error_type("Qdrant host configuration requires a port between 1 and 65535.")
    elif port is not None:
        raise error_type("Qdrant port requires a non-empty host.")

    if not has_remote and not has_path:
        raise error_type("Qdrant requires a non-empty url, host and port, or an explicit local path.")
    if has_url and has_host:
        raise error_type("Qdrant url and host/port modes cannot be configured together.")
    if has_remote and has_path:
        raise error_type("Qdrant remote endpoint and local path modes cannot be configured together.")

    if has_path:
        remote_only = [key for key in ("api_key", "https") if config.get(key) is not None]
        if remote_only:
            raise error_type(
                "Qdrant local path mode cannot use remote-only option(s): " + ", ".join(sorted(remote_only)) + "."
            )
        logging.warning("Qdrant explicit local path mode is enabled; use a remote Qdrant server in production.")


def validate_server_config(config: dict) -> None:
    """Validate server-only invariants after startup/runtime configuration merges."""
    vector_store = config.get("vector_store")
    if not isinstance(vector_store, dict) or vector_store.get("provider") != "qdrant":
        return

    qdrant_config = vector_store.get("config")
    if not isinstance(qdrant_config, dict):
        raise ValueError("Qdrant vector-store configuration must be a JSON object.")
    _validate_qdrant_config(qdrant_config, error_type=ValueError)


def sanitized_validation_error_message(exc: ValidationError) -> str:
    """Render Pydantic errors without their input values, which may contain credentials."""
    issues = []
    for error in exc.errors(include_url=False, include_context=False, include_input=False):
        location = ".".join(str(part) for part in error.get("loc", ())) or "configuration"
        issues.append(f"{location}: {error.get('msg', 'Invalid value')}")
    return "Invalid configuration" + (f": {'; '.join(issues)}" if issues else ".")


def build_vector_store_config(environ: Mapping[str, str]) -> tuple[dict, set[str]]:
    """Build the REST server vector-store config and environment lock set.

    Direct SDK defaults remain unchanged. This strict parser applies only when
    the REST server is explicitly configured through generic vector-store
    environment variables.
    """
    provider_is_set = "VECTOR_STORE_PROVIDER" in environ
    config_is_set = "VECTOR_STORE_CONFIG" in environ
    locked_components = {"vector_store"} if provider_is_set or config_is_set else set()

    if config_is_set and not provider_is_set:
        raise RuntimeError("VECTOR_STORE_PROVIDER is required when VECTOR_STORE_CONFIG is set.")

    provider = environ.get("VECTOR_STORE_PROVIDER", "pgvector").strip().lower()
    if not provider:
        raise RuntimeError("VECTOR_STORE_PROVIDER must not be empty.")

    if config_is_set:
        config = _parse_json_object(environ["VECTOR_STORE_CONFIG"])
    elif provider == "pgvector":
        config = {
            "host": environ.get("POSTGRES_HOST", "postgres"),
            "port": int(environ.get("POSTGRES_PORT", "5432")),
            "dbname": environ.get("POSTGRES_DB", "postgres"),
            "user": environ.get("POSTGRES_USER", "postgres"),
            "password": environ.get("POSTGRES_PASSWORD", "postgres"),
        }
    else:
        raise RuntimeError(f"VECTOR_STORE_CONFIG is required when VECTOR_STORE_PROVIDER is '{provider}'.")

    config = deepcopy(config)
    config.setdefault("collection_name", _collection_name(environ))

    if provider == "qdrant":
        _validate_qdrant_config(config)

    return {"provider": provider, "config": config}, locked_components
