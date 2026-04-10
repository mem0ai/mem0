"""Pytest configuration: allow imports when the distribution is not installed (e.g. local pytest)."""

import importlib.metadata
import sys
import types
from unittest.mock import MagicMock

# Optional dependencies (only stub when missing so real packages stay usable in integration tests).
try:
    import posthog  # noqa: F401
except ImportError:
    if "posthog" not in sys.modules:
        sys.modules["posthog"] = MagicMock()

try:
    import qdrant_client  # noqa: F401
except ImportError:
    _qdrant = types.ModuleType("qdrant_client")
    _qdrant.QdrantClient = MagicMock()
    sys.modules.setdefault("qdrant_client", _qdrant)

try:
    importlib.metadata.version("mem0ai")
except importlib.metadata.PackageNotFoundError:
    _real_version = importlib.metadata.version

    def _version_with_mem0ai_fallback(dist_name: str) -> str:
        if dist_name == "mem0ai":
            return "0.0.0-dev"
        return _real_version(dist_name)

    importlib.metadata.version = _version_with_mem0ai_fallback  # type: ignore[assignment]
