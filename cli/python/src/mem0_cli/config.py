"""Configuration management for mem0 CLI.

Config precedence (highest to lowest):
1. CLI flags (--api-key, --base-url, etc.)
2. Environment variables (MEM0_API_KEY, etc.)
3. Config file (~/.mem0/config.json)
4. Defaults
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".mem0"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_BASE_URL = "https://api.mem0.ai"
CONFIG_VERSION = 1


@dataclass
class PlatformConfig:
    api_key: str = ""
    base_url: str = DEFAULT_BASE_URL
    user_email: str = ""
    # Agent Mode (unclaimed-shadow signup)
    agent_mode: bool = False  # True while the key is an unclaimed agent-mode key
    created_via: str = ""  # "agent_mode" | "email" | "api_key" | "existing_key"
    agent_caller: str = (
        ""  # canonical agent name when created_via == "agent_mode" (e.g. "claude-code")
    )
    claimed_at: str = ""  # ISO timestamp once the agent has been claimed by a human
    default_user_id: str = ""  # `user_<slug>` returned by bootstrap; used as auto-default


@dataclass
class DefaultsConfig:
    user_id: str = ""
    agent_id: str = ""
    app_id: str = ""
    run_id: str = ""


@dataclass
class TelemetryConfig:
    anonymous_id: str = ""


@dataclass
class Mem0Config:
    version: int = CONFIG_VERSION
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    platform: PlatformConfig = field(default_factory=PlatformConfig)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)


SHORT_KEY_ALIASES: dict[str, str] = {
    "api_key": "platform.api_key",
    "base_url": "platform.base_url",
    "user_email": "platform.user_email",
    "user_id": "defaults.user_id",
    "agent_id": "defaults.agent_id",
    "app_id": "defaults.app_id",
    "run_id": "defaults.run_id",
}


def ensure_config_dir() -> Path:
    """Create ~/.mem0 directory with secure permissions if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG_DIR, stat.S_IRWXU)  # 0700
    return CONFIG_DIR


def load_config() -> Mem0Config:
    """Load config from file, applying env var overrides."""
    config = Mem0Config()

    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            data = json.load(f)

        config.version = data.get("version", CONFIG_VERSION)

        plat = data.get("platform", {})
        config.platform.api_key = plat.get("api_key", "")
        config.platform.base_url = plat.get("base_url", DEFAULT_BASE_URL)
        config.platform.user_email = plat.get("user_email", "")
        config.platform.agent_mode = bool(plat.get("agent_mode", False))
        config.platform.created_via = plat.get("created_via", "")
        config.platform.agent_caller = plat.get("agent_caller", "")
        config.platform.claimed_at = plat.get("claimed_at", "")
        config.platform.default_user_id = plat.get("default_user_id", "")

        defaults = data.get("defaults", {})
        config.defaults.user_id = defaults.get("user_id", "")
        config.defaults.agent_id = defaults.get("agent_id", "")
        config.defaults.app_id = defaults.get("app_id", "")
        config.defaults.run_id = defaults.get("run_id", "")
        telemetry = data.get("telemetry", {})
        config.telemetry.anonymous_id = telemetry.get("anonymous_id", "")

    # Environment variable overrides
    env_key = os.environ.get("MEM0_API_KEY")
    if env_key:
        config.platform.api_key = env_key

    env_base = os.environ.get("MEM0_BASE_URL")
    if env_base:
        config.platform.base_url = env_base

    env_user_id = os.environ.get("MEM0_USER_ID")
    if env_user_id:
        config.defaults.user_id = env_user_id

    env_agent_id = os.environ.get("MEM0_AGENT_ID")
    if env_agent_id:
        config.defaults.agent_id = env_agent_id

    env_app_id = os.environ.get("MEM0_APP_ID")
    if env_app_id:
        config.defaults.app_id = env_app_id

    env_run_id = os.environ.get("MEM0_RUN_ID")
    if env_run_id:
        config.defaults.run_id = env_run_id

    return config


def save_config(config: Mem0Config) -> None:
    """Write config to disk with secure permissions."""
    ensure_config_dir()

    data: dict[str, Any] = {
        "version": config.version,
        "defaults": {
            "user_id": config.defaults.user_id,
            "agent_id": config.defaults.agent_id,
            "app_id": config.defaults.app_id,
            "run_id": config.defaults.run_id,
        },
        "platform": {
            "api_key": config.platform.api_key,
            "base_url": config.platform.base_url,
            "user_email": config.platform.user_email,
            "agent_mode": config.platform.agent_mode,
            "created_via": config.platform.created_via,
            "agent_caller": config.platform.agent_caller,
            "claimed_at": config.platform.claimed_at,
            "default_user_id": config.platform.default_user_id,
        },
        "telemetry": {
            "anonymous_id": config.telemetry.anonymous_id,
        },
    }

    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

    os.chmod(CONFIG_FILE, stat.S_IRUSR | stat.S_IWUSR)  # 0600

    # Propagate the active api_key to ecosystem touchpoints (Claude Code
    # plugin env injection, shell rc exports). Idempotent — only updates
    # EXISTING entries; never creates new ones. Best-effort: any IOError
    # in the sync is swallowed so config.json is always the authoritative
    # write, never blocked by plugin-state issues.
    if config.platform.api_key:
        try:
            from mem0_cli.plugin_sync import sync_api_key

            sync_api_key(config.platform.api_key)
        except Exception:
            pass


def redact_key(key: str) -> str:
    """Redact an API key for display: m0-xxx...xxx"""
    if not key:
        return "(not set)"
    if len(key) <= 8:
        return key[:2] + "***"
    return key[:4] + "..." + key[-4:]


def get_nested_value(config: Mem0Config, dotted_key: str) -> Any:
    """Get a config value by dotted path, e.g. 'platform.api_key' or short form 'api_key'."""
    dotted_key = SHORT_KEY_ALIASES.get(dotted_key, dotted_key)
    parts = dotted_key.split(".")
    obj: Any = config
    for part in parts:
        if hasattr(obj, part):
            obj = getattr(obj, part)
        else:
            return None
    return obj


def set_nested_value(config: Mem0Config, dotted_key: str, value: str) -> bool:
    """Set a config value by dotted path. Returns True on success."""
    dotted_key = SHORT_KEY_ALIASES.get(dotted_key, dotted_key)
    parts = dotted_key.split(".")
    obj: Any = config
    for part in parts[:-1]:
        if hasattr(obj, part):
            obj = getattr(obj, part)
        else:
            return False

    final_key = parts[-1]
    if not hasattr(obj, final_key):
        return False

    current = getattr(obj, final_key)
    # Type coercion
    if isinstance(current, bool):
        value = value.lower() in ("true", "1", "yes")  # type: ignore[assignment]
    elif isinstance(current, int):
        value = int(value)  # type: ignore[assignment]

    setattr(obj, final_key, value)
    return True
