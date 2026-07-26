"""Regression test for openmemory's ``get_memory_client`` routing.

Guards against re-routing the openmemory "Custom Instructions" text (which the
UI + the ``ConfigModel.value["openmemory"]["custom_instructions"]`` DB key both
name ``custom_instructions``) into mem0's ``custom_fact_extraction_prompt``
slot. That slot is a FULL override of the extraction system prompt and shifts
JSON-contract ownership to the caller — silently sending short freeform text
into it breaks the extraction pipeline. openmemory's short instructions must
land in ``custom_instructions`` instead, which appends guidance to the user
prompt while leaving the built-in system prompt (and its JSON contract)
untouched.

See mem0 PR #6288 / issue #5730.

This test stubs the heavy ``app.database`` and ``app.models`` imports through
``sys.modules`` so it can exercise ``app.utils.memory.get_memory_client`` in
isolation — no database, no FastAPI, no real LLM required.
"""

import importlib
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub heavy imports BEFORE ``app.utils.memory`` is loaded.
# ``app.utils.memory`` does ``from app.database import SessionLocal`` and
# ``from app.models import Config as ConfigModel`` at import time; both pull in
# SQLAlchemy + declarative_base + dotenv, which we don't need for this test.
# ---------------------------------------------------------------------------

os.environ.setdefault("OPENAI_API_KEY", "test-key")

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))


def _install_app_stubs() -> None:
    """Register minimal ``app.database`` + ``app.models`` stubs in sys.modules."""
    # Real ``app`` package — reuse it if already imported so we don't clobber
    # anything a sibling test set up.
    app_pkg = sys.modules.get("app")
    if app_pkg is None:
        app_pkg = types.ModuleType("app")
        app_pkg.__path__ = [str(_API_ROOT / "app")]  # mark as a package
        sys.modules["app"] = app_pkg

    # Stub app.database
    database_stub = types.ModuleType("app.database")
    database_stub.SessionLocal = MagicMock(name="SessionLocalStub")
    sys.modules["app.database"] = database_stub
    app_pkg.database = database_stub  # type: ignore[attr-defined]

    # Stub app.models with a ``Config`` class the module imports as ``ConfigModel``.
    models_stub = types.ModuleType("app.models")

    class _ConfigStub:  # noqa: D401 — plain stub
        """Stand-in for the real SQLAlchemy ``Config`` model."""
        key = None
        value = None

    models_stub.Config = _ConfigStub
    sys.modules["app.models"] = models_stub
    app_pkg.models = models_stub  # type: ignore[attr-defined]


# ``om_memory`` is populated by the module-scoped ``_stubbed_app_module``
# fixture below, which installs the stubs, imports the target module against
# them, and then restores ``sys.modules``. Doing the stubbing at import time
# would leave the partial ``app.database`` / ``app.models`` stubs in the global
# ``sys.modules`` forever, breaking any sibling module (e.g. ``test_mcp_server``)
# that later imports the *real* ``app.models`` (``Memory``, ``MemoryAccessLog``).
om_memory = None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def _stubbed_app_module():
    """Import ``app.utils.memory`` against the stubs, then restore ``sys.modules``.

    Snapshots every ``app`` entry we touch (and the ``app`` package attributes
    the stubber mutates), installs the stubs, imports the target module, and on
    teardown restores the snapshot so the stubs never leak past this module.
    """
    global om_memory

    _MISSING = object()
    tracked = ("app", "app.database", "app.models", "app.utils", "app.utils.memory")
    saved_modules = {name: sys.modules.get(name) for name in tracked}
    app_pkg = saved_modules["app"]
    saved_attrs = (
        {name: getattr(app_pkg, name, _MISSING) for name in ("database", "models")}
        if app_pkg is not None
        else {}
    )

    _install_app_stubs()
    try:
        om_memory = importlib.import_module("app.utils.memory")
        yield om_memory
    finally:
        om_memory = None
        for name in tracked:
            original = saved_modules[name]
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
        for name, value in saved_attrs.items():
            if value is _MISSING:
                if hasattr(app_pkg, name):
                    delattr(app_pkg, name)
            else:
                setattr(app_pkg, name, value)


@pytest.fixture(autouse=True)
def _reset_module_state():
    """Reset ``get_memory_client`` module-level cache before each test."""
    om_memory._memory_client = None
    om_memory._config_hash = None
    yield
    om_memory._memory_client = None
    om_memory._config_hash = None


@pytest.fixture
def empty_db():
    """Wire ``SessionLocal`` so the DB-config lookup returns ``None``.

    ``get_memory_client`` calls ``db.query(ConfigModel).filter(...).first()``.
    Returning ``None`` from ``.first()`` forces the "no DB config" branch, so
    the ONLY source of custom instructions is the function argument.
    """
    session = MagicMock(name="Session")
    session.query.return_value.filter.return_value.first.return_value = None
    om_memory.SessionLocal = MagicMock(return_value=session)
    yield session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _capture_from_config_calls():
    """Patch ``Memory.from_config`` to record the config dict it was called with.

    ``get_memory_client`` calls ``Memory.from_config(config_dict=config)``; the
    patched version returns a sentinel client so the rest of the function's
    success path executes.
    """
    captured: dict = {}

    def _fake_from_config(config_dict):
        captured["config"] = config_dict
        return MagicMock(name="MemoryClientStub")

    return captured, _fake_from_config


class TestGetMemoryClientRoutesCustomInstructions:
    def test_custom_instructions_arg_routes_to_custom_instructions_key(self, empty_db):
        """The ``custom_instructions`` arg must land in ``config['custom_instructions']``.

        It must NOT be written to ``custom_fact_extraction_prompt`` (which is
        mem0's full-override slot and would silently break the JSON contract).
        """
        captured, fake_from_config = _capture_from_config_calls()

        with patch.object(om_memory.Memory, "from_config", side_effect=fake_from_config):
            client = om_memory.get_memory_client("be concise")

        assert client is not None, "expected a memory client stub, not None"

        cfg = captured.get("config")
        assert cfg is not None, "Memory.from_config was never called"

        # The core assertion — routes to the append-only slot, not the full-override slot.
        assert cfg.get("custom_instructions") == "be concise", (
            "expected openmemory instructions to land in config['custom_instructions'] "
            f"(append-only), got: {cfg.get('custom_instructions')!r}"
        )
        assert "custom_fact_extraction_prompt" not in cfg, (
            "openmemory's short instructions text must NOT be routed into "
            "config['custom_fact_extraction_prompt'] — that slot fully overrides "
            "the extraction system prompt and would break the JSON output contract"
        )

    def test_no_instructions_writes_neither_key(self, empty_db):
        """When no instructions are provided, neither key should be set."""
        captured, fake_from_config = _capture_from_config_calls()

        with patch.object(om_memory.Memory, "from_config", side_effect=fake_from_config):
            om_memory.get_memory_client(None)

        cfg = captured["config"]
        assert "custom_instructions" not in cfg
        assert "custom_fact_extraction_prompt" not in cfg

    def test_db_instructions_also_route_to_custom_instructions_key(self):
        """The DB-supplied instructions must follow the same routing.

        ``ConfigModel.value["openmemory"]["custom_instructions"]`` is the DB
        source of the same short freeform text; it must land in the same
        append-only slot as the function-arg path.
        """
        db_config = MagicMock(name="DBConfig")
        db_config.value = {
            "openmemory": {"custom_instructions": "prefer bullet points"},
        }
        session = MagicMock(name="Session")
        session.query.return_value.filter.return_value.first.return_value = db_config
        om_memory.SessionLocal = MagicMock(return_value=session)

        captured, fake_from_config = _capture_from_config_calls()

        with patch.object(om_memory.Memory, "from_config", side_effect=fake_from_config):
            om_memory.get_memory_client(None)

        cfg = captured["config"]
        assert cfg.get("custom_instructions") == "prefer bullet points"
        assert "custom_fact_extraction_prompt" not in cfg

    def test_arg_takes_precedence_over_db(self):
        """Function-arg wins over DB value, and still lands in the correct slot."""
        db_config = MagicMock(name="DBConfig")
        db_config.value = {
            "openmemory": {"custom_instructions": "from db"},
        }
        session = MagicMock(name="Session")
        session.query.return_value.filter.return_value.first.return_value = db_config
        om_memory.SessionLocal = MagicMock(return_value=session)

        captured, fake_from_config = _capture_from_config_calls()

        with patch.object(om_memory.Memory, "from_config", side_effect=fake_from_config):
            om_memory.get_memory_client("from arg")

        cfg = captured["config"]
        assert cfg.get("custom_instructions") == "from arg"
        assert "custom_fact_extraction_prompt" not in cfg
