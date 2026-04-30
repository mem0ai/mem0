import json
import logging
import os
import uuid

# Set up the directory path
VECTOR_ID = str(uuid.uuid4())
home_dir = os.path.expanduser("~")
mem0_dir = os.environ.get("MEM0_DIR") or os.path.join(home_dir, ".mem0")
os.makedirs(mem0_dir, exist_ok=True)

_logger = logging.getLogger(__name__)


def _config_path():
    return os.path.join(mem0_dir, "config.json")


def _load_config():
    """Load ~/.mem0/config.json, returning {} on missing/malformed file."""
    path = _config_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        _logger.debug("Failed to load mem0 config %s: %s", path, e)
        return {}


def _write_config(config):
    """Best-effort write of ~/.mem0/config.json. Never raises."""
    path = _config_path()
    try:
        with open(path, "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        _logger.debug("Failed to write mem0 config %s: %s", path, e)


def setup_config():
    """Ensure ~/.mem0/config.json exists with a top-level user_id.

    Idempotent: backfills user_id for users whose config was written by the
    CLI (which writes telemetry.anonymous_id but no top-level user_id).
    Without this, OSS Python telemetry is silently dropped because
    get_user_id() returns None when user_id is missing.
    """
    config = _load_config()
    if config.get("user_id"):
        return
    config["user_id"] = str(uuid.uuid4())
    _write_config(config)


def get_user_id():
    config = _load_config()
    if not config:
        return "anonymous_user"
    return config.get("user_id")


def read_anon_ids():
    """Return both anon IDs and the aliased_to flag from ~/.mem0/config.json.

    Returns a dict with keys "oss", "cli", "aliased_to" (any may be None).
    OSS Python writes top-level "user_id"; the CLI writes
    "telemetry.anonymous_id". They may coexist depending on which surface
    ran first.
    """
    config = _load_config()
    telemetry = config.get("telemetry") if isinstance(config.get("telemetry"), dict) else {}
    return {
        "oss": config.get("user_id"),
        "cli": telemetry.get("anonymous_id"),
        "aliased_to": telemetry.get("aliased_to"),
    }


def mark_aliased(email):
    """Persist telemetry.aliased_to = email so $identify only fires once."""
    config = _load_config()
    telemetry = config.get("telemetry")
    if not isinstance(telemetry, dict):
        telemetry = {}
    telemetry["aliased_to"] = email
    config["telemetry"] = telemetry
    _write_config(config)


def get_or_create_user_id(vector_store=None):
    """Store user_id in vector store and return it.

    If vector_store is None, simply returns the user_id from config.
    This ensures telemetry initialization never fails due to missing vector store.
    """
    user_id = get_user_id()

    # If no vector store provided, just return the user_id
    if vector_store is None:
        return user_id

    # Try to get existing user_id from vector store
    try:
        existing = vector_store.get(vector_id=user_id)
        if existing and hasattr(existing, "payload") and existing.payload and "user_id" in existing.payload:
            stored_id = existing.payload["user_id"]
            # Ensure we never return None from vector store
            if stored_id is not None:
                return stored_id
    except Exception:
        pass

    # If we get here, we need to insert the user_id
    try:
        dims = getattr(vector_store, "embedding_model_dims", 1536)
        vector_store.insert(
            vectors=[[0.1] * dims], payloads=[{"user_id": user_id, "type": "user_identity"}], ids=[user_id]
        )
    except Exception:
        pass

    return user_id
