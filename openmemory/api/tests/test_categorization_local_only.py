"""Local-first guarantees for auto-categorization.

Auto-categorization uses OpenAI (cloud). Two invariants must hold for the team
local-first install:

1. Importing ``app.utils.categorization`` must NOT require OpenAI credentials —
   it used to build ``OpenAI()`` at module import, which crashed the whole API
   at startup when no ``OPENAI_API_KEY`` was set (the local-first default).
2. In fail-closed local-only mode (``MEM0_LOCAL_ONLY``) categorization must
   never egress to OpenAI — it returns no categories and the memory is still
   saved. The same happens when no credentials are available.

No network access in any of these tests.
"""

import importlib

from app.utils import categorization


def _reset_client():
    categorization._openai_client = None


def test_import_does_not_require_openai_credentials(monkeypatch):
    # No module-level OpenAI() — re-importing without a key must not raise.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    importlib.reload(categorization)
    assert hasattr(categorization, "get_categories_for_memory")


def test_local_only_skips_categorization_without_building_client(monkeypatch):
    monkeypatch.setenv("MEM0_LOCAL_ONLY", "1")
    _reset_client()

    def _boom():
        raise AssertionError("OpenAI client must not be built in local-only mode")

    monkeypatch.setattr(categorization, "_get_openai_client", _boom)
    assert categorization.get_categories_for_memory("algum conteúdo") == []


def test_no_credentials_returns_empty(monkeypatch):
    monkeypatch.setenv("MEM0_LOCAL_ONLY", "0")
    _reset_client()

    def _raise(*args, **kwargs):
        raise categorization.OpenAIError("missing credentials")

    # Lazy client build fails (no creds) -> categorization is a no-op, not a crash.
    monkeypatch.setattr(categorization, "OpenAI", _raise)
    assert categorization.get_categories_for_memory("algum conteúdo") == []


def test_local_only_flag_parsing(monkeypatch):
    # is_local_only is now the canonical function imported from app.utils.env;
    # it's still accessible via categorization.is_local_only after the refactor.
    for truthy in ("1", "true", "YES", "on"):
        monkeypatch.setenv("MEM0_LOCAL_ONLY", truthy)
        assert categorization.is_local_only() is True
    for falsy in ("0", "false", ""):
        monkeypatch.setenv("MEM0_LOCAL_ONLY", falsy)
        assert categorization.is_local_only() is False
    monkeypatch.delenv("MEM0_LOCAL_ONLY", raising=False)
    assert categorization.is_local_only() is False
