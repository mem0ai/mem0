"""Regression test for #4279: vector store path defaults to /tmp/{provider}, which
fails or silently loses data in macOS LaunchAgents, systemd services, Docker, etc.
"""
import os
import sys
from unittest.mock import patch

import pytest

from mem0.vector_stores.configs import VectorStoreConfig


def test_default_path_is_not_tmp():
    """The default path must not be /tmp/{provider} on any platform."""
    cfg = VectorStoreConfig(provider="faiss", config={})
    path = cfg.config.path
    assert path is not None
    assert not path.startswith("/tmp/"), f"default path still falls back to /tmp: {path}"
    assert path.endswith("faiss")


def test_env_var_override():
    """MEM0_DATA_DIR must override the platform default."""
    with patch.dict(os.environ, {"MEM0_DATA_DIR": "/var/lib/mem0_test"}):
        cfg = VectorStoreConfig(provider="faiss", config={})
        assert cfg.config.path == os.path.join("/var/lib/mem0_test", "faiss")


def test_explicit_path_wins():
    """An explicit path in the user config must beat both the env var and the default."""
    with patch.dict(os.environ, {"MEM0_DATA_DIR": "/should/not/leak"}):
        cfg = VectorStoreConfig(provider="faiss", config={"path": "/explicit/user/path"})
        assert cfg.config.path == "/explicit/user/path"


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific default")
def test_macos_default_uses_application_support():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("MEM0_DATA_DIR", None)
        cfg = VectorStoreConfig(provider="faiss", config={})
        assert "Application Support/mem0" in cfg.config.path


@pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific default")
def test_linux_default_respects_xdg_data_home():
    with patch.dict(os.environ, {"XDG_DATA_HOME": "/custom/xdg"}):
        os.environ.pop("MEM0_DATA_DIR", None)
        cfg = VectorStoreConfig(provider="faiss", config={})
        assert cfg.config.path == os.path.join("/custom/xdg", "mem0", "faiss")
