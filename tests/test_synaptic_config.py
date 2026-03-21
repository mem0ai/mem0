"""Tests for synaptic-related fields in MemoryConfig."""
import os
from unittest.mock import patch

import pytest

from mem0.configs.base import MemoryConfig


def test_config_defaults():
    """enable_synaptic is False and synaptic_db_dir is None when env vars are unset."""
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("SYNAPTIC_ENABLED", None)
        os.environ.pop("SYNAPTIC_DB_DIR", None)
        cfg = MemoryConfig()
        assert cfg.enable_synaptic is False
        assert cfg.synaptic_db_dir is None


def test_config_from_env_vars():
    """enable_synaptic and synaptic_db_dir pick up env vars as defaults."""
    with patch.dict(os.environ, {"SYNAPTIC_ENABLED": "true", "SYNAPTIC_DB_DIR": "/data/syn"}):
        cfg = MemoryConfig()
        assert cfg.enable_synaptic is True
        assert cfg.synaptic_db_dir == "/data/syn"


def test_config_enable():
    """MemoryConfig(enable_synaptic=True) is accepted and stored correctly."""
    cfg = MemoryConfig(enable_synaptic=True)
    assert cfg.enable_synaptic is True


def test_config_synaptic_db_dir():
    """synaptic_db_dir can be set to a custom path."""
    cfg = MemoryConfig(synaptic_db_dir="/tmp/synaptic_test")
    assert cfg.synaptic_db_dir == "/tmp/synaptic_test"


def test_config_both_synaptic_fields():
    """Both synaptic fields can be set together."""
    cfg = MemoryConfig(enable_synaptic=True, synaptic_db_dir="/data/syn")
    assert cfg.enable_synaptic is True
    assert cfg.synaptic_db_dir == "/data/syn"
