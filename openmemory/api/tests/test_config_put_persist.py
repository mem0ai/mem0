"""Regression: PUT /api/v1/config/ must persist and return the updated config.

Closes mem0ai/mem0#6353. Builds on salvage of @okyashgajjar #6356.

Loads the router module directly (avoids package__init__ dependency chain)
so CI/dev can run these without full openmemory stack install.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _load_config_router():
    """Import app.routers.config without importing app.routers package side effects."""
    api_root = Path(__file__).resolve().parents[1]
    # Ensure `app` package path for relative absolute imports inside the module
    if str(api_root) not in sys.path:
        sys.path.insert(0, str(api_root))

    # Stub only heavy transitive deps if missing (will work with real installs too)
    for modname in (
        "app.database",
        "app.models",
        "app.utils.memory",
    ):
        if modname not in sys.modules:
            stub = types.ModuleType(modname)
            if modname == "app.database":
                stub.get_db = MagicMock()
            if modname == "app.models":
                class Config:  # minimal stand-in
                    pass
                stub.Config = Config
            if modname == "app.utils.memory":
                stub.reset_memory_client = MagicMock()
            # parent packages
            parts = modname.split(".")
            for i in range(1, len(parts)):
                parent = ".".join(parts[:i])
                if parent not in sys.modules:
                    sys.modules[parent] = types.ModuleType(parent)
            sys.modules[modname] = stub

    path = api_root / "app" / "routers" / "config.py"
    spec = importlib.util.spec_from_file_location("app.routers.config_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.asyncio
async def test_put_configuration_saves_and_resets_client():
    """PUT must call save_config_to_db + reset_memory_client and return body."""
    config_router = _load_config_router()

    current = {
        "openmemory": {"custom_instructions": None},
        "mem0": {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "gpt-4o-mini",
                    "temperature": 0.1,
                    "max_tokens": 2000,
                    "api_key": "env:OPENAI_API_KEY",
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small",
                    "api_key": "env:OPENAI_API_KEY",
                },
            },
            "vector_store": None,
        },
    }

    openmemory_payload = config_router.OpenMemoryConfig(
        custom_instructions="Test instructions"
    )
    llm = config_router.LLMProvider(
        provider="openai",
        config=config_router.LLMConfig(
            model="gpt-4o",
            temperature=0.5,
            max_tokens=4000,
        ),
    )
    body = config_router.ConfigSchema(
        openmemory=openmemory_payload,
        mem0=config_router.Mem0Config(llm=llm, embedder=None, vector_store=None),
    )
    db = MagicMock()

    with (
        patch.object(config_router, "get_config_from_db", return_value=current.copy()) as get_cfg,
        patch.object(config_router, "save_config_to_db", side_effect=lambda db, cfg: cfg) as save_cfg,
        patch.object(config_router, "reset_memory_client") as reset_client,
    ):
        result = await config_router.update_configuration(body, db)

    get_cfg.assert_called_once_with(db)
    save_cfg.assert_called_once()
    saved = save_cfg.call_args.args[1]
    assert saved["openmemory"]["custom_instructions"] == "Test instructions"
    assert saved["mem0"]["llm"]["provider"] == "openai"
    assert saved["mem0"]["llm"]["config"]["model"] == "gpt-4o"
    reset_client.assert_called_once()
    assert result is saved
    assert result["openmemory"]["custom_instructions"] == "Test instructions"


@pytest.mark.asyncio
async def test_put_configuration_allows_omitted_mem0():
    """If mem0 is omitted, PUT should keep prior mem0 and still persist openmemory."""
    config_router = _load_config_router()

    current = {
        "openmemory": {"custom_instructions": "old"},
        "mem0": {"llm": {"provider": "openai", "config": {"model": "keep-me"}}},
    }
    body = config_router.ConfigSchema(
        openmemory=config_router.OpenMemoryConfig(custom_instructions="new"),
        mem0=None,
    )
    db = MagicMock()

    with (
        patch.object(config_router, "get_config_from_db", return_value=current.copy()),
        patch.object(config_router, "save_config_to_db", side_effect=lambda db, cfg: cfg) as save_cfg,
        patch.object(config_router, "reset_memory_client") as reset_client,
    ):
        result = await config_router.update_configuration(body, db)

    saved = save_cfg.call_args.args[1]
    assert saved["openmemory"]["custom_instructions"] == "new"
    assert saved["mem0"]["llm"]["config"]["model"] == "keep-me"
    reset_client.assert_called_once()
    assert result["mem0"]["llm"]["config"]["model"] == "keep-me"
