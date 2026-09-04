"""Regression tests for mem0 package initialization."""

import importlib
import importlib.metadata
import sys


def test_version_fallback_when_distribution_metadata_missing(monkeypatch):
    """mem0 falls back to a sentinel version without installed dist metadata."""
    real_version = importlib.metadata.version

    def fake_version(distribution_name):
        if distribution_name == "mem0ai":
            raise importlib.metadata.PackageNotFoundError(distribution_name)
        return real_version(distribution_name)

    monkeypatch.setattr(importlib.metadata, "version", fake_version)

    cached_mem0 = sys.modules.pop("mem0", None)
    try:
        imported = importlib.import_module("mem0")
        assert imported.__version__ == "0.0.0+unknown"
    finally:
        sys.modules.pop("mem0", None)
        if cached_mem0 is not None:
            sys.modules["mem0"] = cached_mem0
