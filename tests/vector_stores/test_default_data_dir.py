"""Tests for OS-appropriate default data directory (issue #4279)."""

import os
import sys
import unittest
from unittest.mock import patch

from mem0.vector_stores.configs import _default_data_dir


class TestDefaultDataDir(unittest.TestCase):
    """Verify _default_data_dir returns OS-appropriate paths."""

    def test_mem0_data_dir_env_override(self):
        """MEM0_DATA_DIR env var should override platform defaults."""
        with patch.dict(os.environ, {"MEM0_DATA_DIR": "/custom/data"}):
            result = _default_data_dir("qdrant")
            self.assertEqual(result, "/custom/data/qdrant")

    def test_mem0_data_dir_env_different_provider(self):
        """MEM0_DATA_DIR should work with any provider name."""
        with patch.dict(os.environ, {"MEM0_DATA_DIR": "/data"}, clear=False):
            result = _default_data_dir("chroma")
            self.assertEqual(result, "/data/chroma")

    @patch("sys.platform", "linux")
    def test_linux_xdg_data_home(self):
        """Linux with XDG_DATA_HOME set should use it."""
        env = {"XDG_DATA_HOME": "/home/user/.data"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("MEM0_DATA_DIR", None)
            result = _default_data_dir("qdrant")
            self.assertEqual(result, "/home/user/.data/mem0/qdrant")

    @patch("sys.platform", "linux")
    def test_linux_default_without_xdg(self):
        """Linux without XDG_DATA_HOME should use ~/.local/share/mem0."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MEM0_DATA_DIR", None)
            os.environ.pop("XDG_DATA_HOME", None)
            result = _default_data_dir("qdrant")
            self.assertIn(".local/share/mem0/qdrant", result)

    @patch("sys.platform", "darwin")
    def test_macos_default(self):
        """macOS should use ~/Library/Application Support/mem0."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MEM0_DATA_DIR", None)
            result = _default_data_dir("chroma")
            self.assertIn("Library/Application Support/mem0/chroma", result)

    @patch("sys.platform", "win32")
    def test_windows_localappdata(self):
        """Windows with LOCALAPPDATA should use it."""
        env = {"LOCALAPPDATA": "C:\\Users\\user\\AppData\\Local"}
        with patch.dict(os.environ, env, clear=False):
            os.environ.pop("MEM0_DATA_DIR", None)
            result = _default_data_dir("qdrant")
            self.assertIn("mem0", result)
            self.assertIn("qdrant", result)

    def test_no_tmp_in_default_path(self):
        """Default path should never be /tmp (the whole point of issue #4279)."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MEM0_DATA_DIR", None)
            result = _default_data_dir("qdrant")
            self.assertNotIn("/tmp/", result)
