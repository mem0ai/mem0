"""Tests for reranker config validation and BUNDLED_RERANKER_PROVIDERS in server/main.py."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")

# server/ modules use bare imports (import telemetry, from auth import ...), so
# the server directory itself must be importable, mirroring how it runs in
# Docker. Mirrors tests/test_api_keys_router.py's guard.
_SERVER_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "server")
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

# main.py raises at import time unless auth is configured, and calls
# Memory.from_config(DEFAULT_CONFIG) at module level (which would otherwise try
# to open a real sqlite history db). These tests only exercise the pure
# _validate_bundled_providers() function, so any value/mock works.
os.environ.setdefault("OPENAI_API_KEY", "fake-key")
os.environ.setdefault("AUTH_DISABLED", "true")

from fastapi import HTTPException  # noqa: E402

with patch("mem0.Memory.from_config", return_value=MagicMock()):
    import main as server_main  # noqa: E402


class TestValidateBundledRerankerProvider:
    def test_bundled_provider_passes(self):
        server_main._validate_bundled_providers({"reranker": {"provider": "llm_reranker"}})  # no raise

    def test_non_bundled_provider_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            server_main._validate_bundled_providers({"reranker": {"provider": "cohere"}})
        assert exc_info.value.status_code == 400
        assert "cohere" in exc_info.value.detail
        assert "llm_reranker" in exc_info.value.detail

    def test_no_reranker_key_passes(self):
        server_main._validate_bundled_providers({})  # no raise

    def test_reranker_without_provider_passes(self):
        server_main._validate_bundled_providers({"reranker": {"config": {}}})  # no raise

    def test_does_not_affect_llm_embedder_validation(self):
        with pytest.raises(HTTPException) as exc_info:
            server_main._validate_bundled_providers({"llm": {"provider": "not-a-real-provider"}})
        assert "not-a-real-provider" in exc_info.value.detail
