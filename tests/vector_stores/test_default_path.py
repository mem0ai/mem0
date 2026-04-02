"""Tests for the vector store default path fix (issue #4279).

Verifies that vector store defaults use platform-appropriate persistent directories
instead of /tmp, which is ephemeral and may be inaccessible in restricted environments.
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mem0.vector_stores.configs import VectorStoreConfig, get_default_vector_store_path

# ---------------------------------------------------------------------------
# get_default_vector_store_path unit tests
# ---------------------------------------------------------------------------

class TestGetDefaultVectorStorePath:
    """Tests for the get_default_vector_store_path helper function."""

    def _clean_env(self, monkeypatch):
        """Remove all relevant env vars to get a clean baseline."""
        for var in ("MEM0_DATA_DIR", "XDG_DATA_HOME", "APPDATA"):
            monkeypatch.delenv(var, raising=False)

    def test_default_falls_back_to_local_share(self, monkeypatch):
        """With no env vars set, path should be ~/.local/share/mem0/{provider}."""
        self._clean_env(monkeypatch)
        result = get_default_vector_store_path("qdrant")
        expected = str(Path.home() / ".local" / "share" / "mem0" / "qdrant")
        assert result == expected

    def test_xdg_data_home_respected(self, monkeypatch):
        """XDG_DATA_HOME should be used as the base when set."""
        self._clean_env(monkeypatch)
        monkeypatch.setenv("XDG_DATA_HOME", "/custom/xdg/data")
        result = get_default_vector_store_path("chroma")
        assert result == "/custom/xdg/data/mem0/chroma"

    def test_appdata_respected_on_windows(self, monkeypatch):
        """APPDATA should be used when XDG_DATA_HOME is not set (Windows)."""
        self._clean_env(monkeypatch)
        monkeypatch.setenv("APPDATA", "C:\\Users\\test\\AppData\\Roaming")
        result = get_default_vector_store_path("faiss")
        expected = str(Path("C:\\Users\\test\\AppData\\Roaming") / "mem0" / "faiss")
        assert result == expected

    def test_xdg_takes_precedence_over_appdata(self, monkeypatch):
        """XDG_DATA_HOME should take precedence over APPDATA."""
        self._clean_env(monkeypatch)
        monkeypatch.setenv("XDG_DATA_HOME", "/xdg/path")
        monkeypatch.setenv("APPDATA", "C:\\windows\\path")
        result = get_default_vector_store_path("qdrant")
        assert result == "/xdg/path/mem0/qdrant"

    def test_mem0_data_dir_takes_highest_precedence(self, monkeypatch):
        """MEM0_DATA_DIR should override all other env vars."""
        self._clean_env(monkeypatch)
        monkeypatch.setenv("MEM0_DATA_DIR", "/custom/mem0/data")
        monkeypatch.setenv("XDG_DATA_HOME", "/should/be/ignored")
        monkeypatch.setenv("APPDATA", "C:\\also\\ignored")
        result = get_default_vector_store_path("qdrant")
        assert result == "/custom/mem0/data/qdrant"

    def test_mem0_data_dir_no_extra_mem0_subdir(self, monkeypatch):
        """MEM0_DATA_DIR is already mem0-specific, so no extra 'mem0' subdir."""
        self._clean_env(monkeypatch)
        monkeypatch.setenv("MEM0_DATA_DIR", "/data/mem0")
        result = get_default_vector_store_path("qdrant")
        # Should be /data/mem0/qdrant, NOT /data/mem0/mem0/qdrant
        assert result == "/data/mem0/qdrant"

    def test_different_providers_get_different_paths(self, monkeypatch):
        """Each provider should get its own subdirectory."""
        self._clean_env(monkeypatch)
        qdrant_path = get_default_vector_store_path("qdrant")
        chroma_path = get_default_vector_store_path("chroma")
        faiss_path = get_default_vector_store_path("faiss")
        assert qdrant_path != chroma_path != faiss_path
        assert qdrant_path.endswith("/qdrant")
        assert chroma_path.endswith("/chroma")
        assert faiss_path.endswith("/faiss")

    def test_path_never_contains_tmp(self, monkeypatch):
        """Default path should never be under /tmp (the whole point of #4279)."""
        self._clean_env(monkeypatch)
        for provider in ("qdrant", "chroma", "faiss"):
            result = get_default_vector_store_path(provider)
            assert not result.startswith("/tmp"), f"Provider {provider} still defaults to /tmp: {result}"


# ---------------------------------------------------------------------------
# VectorStoreConfig integration tests
# ---------------------------------------------------------------------------

class TestVectorStoreConfigPathInjection:
    """Tests that VectorStoreConfig correctly injects the new default path."""

    def _clean_env(self, monkeypatch):
        for var in ("MEM0_DATA_DIR", "XDG_DATA_HOME", "APPDATA"):
            monkeypatch.delenv(var, raising=False)

    def test_qdrant_gets_persistent_default_path(self, monkeypatch):
        """Qdrant should get a persistent default path, not /tmp."""
        self._clean_env(monkeypatch)
        vc = VectorStoreConfig(provider="qdrant", config={})
        assert "/tmp" not in vc.config.path
        assert "mem0" in vc.config.path
        assert vc.config.path.endswith("/qdrant")

    def test_explicit_path_not_overridden(self, monkeypatch):
        """An explicitly provided path should be used as-is."""
        self._clean_env(monkeypatch)
        custom_path = "/my/custom/qdrant/path"
        vc = VectorStoreConfig(provider="qdrant", config={"path": custom_path})
        assert vc.config.path == custom_path

    def test_explicit_tmp_path_still_works(self, monkeypatch):
        """Users who explicitly want /tmp should still be able to use it."""
        self._clean_env(monkeypatch)
        vc = VectorStoreConfig(provider="qdrant", config={"path": "/tmp/qdrant"})
        assert vc.config.path == "/tmp/qdrant"

    def test_mem0_data_dir_flows_through_config(self, monkeypatch):
        """MEM0_DATA_DIR should be respected through VectorStoreConfig."""
        self._clean_env(monkeypatch)
        monkeypatch.setenv("MEM0_DATA_DIR", "/custom/data")
        vc = VectorStoreConfig(provider="qdrant", config={})
        assert vc.config.path == "/custom/data/qdrant"

    def test_xdg_data_home_flows_through_config(self, monkeypatch):
        """XDG_DATA_HOME should be respected through VectorStoreConfig."""
        self._clean_env(monkeypatch)
        monkeypatch.setenv("XDG_DATA_HOME", "/xdg/data")
        vc = VectorStoreConfig(provider="qdrant", config={})
        assert vc.config.path == "/xdg/data/mem0/qdrant"


# ---------------------------------------------------------------------------
# Qdrant-specific config tests
# ---------------------------------------------------------------------------

class TestQdrantConfigDefault:
    """Tests that QdrantConfig's own default_factory uses the new path."""

    def _clean_env(self, monkeypatch):
        for var in ("MEM0_DATA_DIR", "XDG_DATA_HOME", "APPDATA"):
            monkeypatch.delenv(var, raising=False)

    def test_qdrant_field_default_is_persistent(self, monkeypatch):
        """QdrantConfig's path Field default should not be /tmp."""
        self._clean_env(monkeypatch)
        from mem0.configs.vector_stores.qdrant import QdrantConfig

        # When path is explicitly provided, the before-validator sees it
        config = QdrantConfig(path=get_default_vector_store_path("qdrant"))
        assert "/tmp" not in config.path
        assert config.path.endswith("/qdrant")

    def test_qdrant_via_vector_store_config_no_path(self, monkeypatch):
        """Creating QdrantConfig via VectorStoreConfig with empty config should work."""
        self._clean_env(monkeypatch)
        vc = VectorStoreConfig(provider="qdrant", config={})
        assert vc.config.path is not None
        assert "/tmp" not in vc.config.path


# ---------------------------------------------------------------------------
# ChromaDB-specific config tests
# ---------------------------------------------------------------------------

class TestChromaDbConfigDefault:
    """Tests that ChromaDB's sentinel check works with the new default path."""

    def _clean_env(self, monkeypatch):
        for var in ("MEM0_DATA_DIR", "XDG_DATA_HOME", "APPDATA"):
            monkeypatch.delenv(var, raising=False)

    def test_chroma_default_path_via_vector_store_config(self, monkeypatch):
        """ChromaDB via VectorStoreConfig should get a non-/tmp default path."""
        self._clean_env(monkeypatch)
        vc = VectorStoreConfig(provider="chroma", config={})
        assert "/tmp" not in vc.config.path
        assert vc.config.path.endswith("/chroma")

    def test_chroma_cloud_config_strips_default_path(self, monkeypatch):
        """ChromaDB cloud config should strip the injected default path."""
        self._clean_env(monkeypatch)
        default_path = get_default_vector_store_path("chroma")
        from mem0.configs.vector_stores.chroma import ChromaDbConfig

        # Simulate what VectorStoreConfig does: inject default path, then create config
        config = ChromaDbConfig(
            path=default_path,
            api_key="test-key",
            tenant="test-tenant",
        )
        # When cloud config is provided and path matches default, path should be stripped
        assert config.path is None

    def test_chroma_explicit_path_with_cloud_raises(self, monkeypatch):
        """ChromaDB with both explicit custom path and cloud config should raise."""
        self._clean_env(monkeypatch)
        from mem0.configs.vector_stores.chroma import ChromaDbConfig

        with pytest.raises(ValueError, match="Cannot specify both"):
            ChromaDbConfig(
                path="/my/custom/path",
                api_key="test-key",
                tenant="test-tenant",
            )


# ---------------------------------------------------------------------------
# FAISS-specific tests
# ---------------------------------------------------------------------------

class TestFaissDefaultPath:
    """Tests that FAISS uses the new default path."""

    def _clean_env(self, monkeypatch):
        for var in ("MEM0_DATA_DIR", "XDG_DATA_HOME", "APPDATA"):
            monkeypatch.delenv(var, raising=False)

    def test_faiss_default_path_via_vector_store_config(self, monkeypatch):
        """FAISS via VectorStoreConfig should get a non-/tmp default path."""
        self._clean_env(monkeypatch)
        vc = VectorStoreConfig(provider="faiss", config={})
        assert "/tmp" not in vc.config.path
        assert vc.config.path.endswith("/faiss")

    def test_faiss_implementation_uses_new_default(self, monkeypatch):
        """FAISS implementation's own fallback should not use /tmp."""
        self._clean_env(monkeypatch)
        with patch("faiss.IndexFlatL2") as mock_index:
            mock_index.return_value = MagicMock()
            with patch("faiss.write_index"):
                from mem0.vector_stores.faiss import FAISS
                store = FAISS(collection_name="test")
                assert "/tmp" not in store.path
                assert "mem0" in store.path


# ---------------------------------------------------------------------------
# Legacy path migration warning tests
# ---------------------------------------------------------------------------

class TestLegacyPathMigration:
    """Tests that legacy /tmp data is automatically migrated to the new path."""

    def _clean_env(self, monkeypatch):
        for var in ("MEM0_DATA_DIR", "XDG_DATA_HOME", "APPDATA"):
            monkeypatch.delenv(var, raising=False)

    def test_auto_migration_copies_legacy_data(self, monkeypatch, tmp_path, caplog):
        """When legacy /tmp/{provider} has data and new path is empty, should copy."""
        self._clean_env(monkeypatch)
        legacy_dir = tmp_path / "legacy_qdrant"
        legacy_dir.mkdir()
        (legacy_dir / "data.bin").write_text("test data")

        new_dir = tmp_path / "new_qdrant"

        from mem0.vector_stores.configs import _migrate_legacy_data

        with patch("mem0.vector_stores.configs.Path") as mock_path_cls:
            real_legacy = Path(str(legacy_dir))

            mock_new_path = MagicMock()
            mock_new_path.exists.return_value = False
            mock_sentinel = MagicMock()
            mock_sentinel.exists.return_value = False
            mock_new_path.__truediv__ = MagicMock(return_value=mock_sentinel)

            mock_path_cls.side_effect = lambda p: real_legacy if "/tmp/" in str(p) else mock_new_path

            with patch("shutil.copytree") as mock_copytree:
                with caplog.at_level(logging.INFO, logger="mem0.vector_stores.configs"):
                    _migrate_legacy_data("qdrant", str(new_dir))

                mock_copytree.assert_called_once()
                assert mock_copytree.call_args[0][1] == str(new_dir)
                assert mock_copytree.call_args[1]["dirs_exist_ok"] is True
                mock_sentinel.touch.assert_called_once()

        assert "migrated" in caplog.text.lower()

    def test_no_migration_when_legacy_path_missing(self, monkeypatch, caplog):
        """Should not migrate when /tmp/{provider} doesn't exist."""
        self._clean_env(monkeypatch)
        from mem0.vector_stores.configs import _migrate_legacy_data

        with patch("mem0.vector_stores.configs.Path") as mock_path_cls:
            mock_legacy_path = MagicMock()
            mock_legacy_path.exists.return_value = False
            mock_path_cls.return_value = mock_legacy_path

            with patch("shutil.copytree") as mock_copytree:
                _migrate_legacy_data("qdrant", "/new/path")
                mock_copytree.assert_not_called()

    def test_no_migration_when_legacy_path_empty_dir(self, monkeypatch, tmp_path, caplog):
        """Should not migrate when /tmp/{provider} exists but is an empty directory."""
        self._clean_env(monkeypatch)
        legacy_dir = tmp_path / "empty_qdrant"
        legacy_dir.mkdir()

        from mem0.vector_stores.configs import _migrate_legacy_data

        with patch("mem0.vector_stores.configs.Path") as mock_path_cls:
            real_legacy = Path(str(legacy_dir))
            mock_path_cls.side_effect = lambda p: real_legacy if "/tmp/" in str(p) else MagicMock()

            with patch("shutil.copytree") as mock_copytree:
                _migrate_legacy_data("qdrant", str(tmp_path / "new"))
                mock_copytree.assert_not_called()

    def test_no_migration_when_legacy_path_is_symlink(self, monkeypatch, tmp_path, caplog):
        """Should refuse to migrate if legacy path is a symlink (security)."""
        self._clean_env(monkeypatch)
        real_dir = tmp_path / "real_data"
        real_dir.mkdir()
        (real_dir / "data.bin").write_text("sensitive")

        symlink_dir = tmp_path / "symlink_qdrant"
        symlink_dir.symlink_to(real_dir)

        from mem0.vector_stores.configs import _migrate_legacy_data

        with patch("mem0.vector_stores.configs.Path") as mock_path_cls:
            real_symlink = Path(str(symlink_dir))
            mock_path_cls.side_effect = lambda p: real_symlink if "/tmp/" in str(p) else MagicMock()

            with patch("shutil.copytree") as mock_copytree:
                _migrate_legacy_data("qdrant", str(tmp_path / "new"))
                mock_copytree.assert_not_called()

    def test_no_migration_when_new_path_already_has_data(self, monkeypatch, tmp_path, caplog):
        """Should not clobber existing data at the new path."""
        self._clean_env(monkeypatch)
        legacy_dir = tmp_path / "legacy"
        legacy_dir.mkdir()
        (legacy_dir / "data.bin").write_text("legacy")

        new_dir = tmp_path / "new"
        new_dir.mkdir()
        (new_dir / "existing.bin").write_text("keep this")

        from mem0.vector_stores.configs import _migrate_legacy_data

        with patch("mem0.vector_stores.configs.Path") as mock_path_cls:
            real_legacy = Path(str(legacy_dir))
            real_new = Path(str(new_dir))

            mock_path_cls.side_effect = lambda p: real_legacy if "/tmp/" in str(p) else real_new

            with patch("shutil.copytree") as mock_copytree:
                with caplog.at_level(logging.INFO, logger="mem0.vector_stores.configs"):
                    _migrate_legacy_data("qdrant", str(new_dir))
                mock_copytree.assert_not_called()

    def test_no_migration_when_sentinel_exists(self, monkeypatch, tmp_path, caplog):
        """Should skip migration when .migration_complete sentinel already exists."""
        self._clean_env(monkeypatch)
        legacy_dir = tmp_path / "legacy"
        legacy_dir.mkdir()
        (legacy_dir / "data.bin").write_text("legacy")

        new_dir = tmp_path / "new"
        new_dir.mkdir()
        (new_dir / ".migration_complete").write_text("")

        from mem0.vector_stores.configs import _migrate_legacy_data

        with patch("mem0.vector_stores.configs.Path") as mock_path_cls:
            real_legacy = Path(str(legacy_dir))
            real_new = Path(str(new_dir))

            mock_path_cls.side_effect = lambda p: real_legacy if "/tmp/" in str(p) else real_new

            with patch("shutil.copytree") as mock_copytree:
                _migrate_legacy_data("qdrant", str(new_dir))
                mock_copytree.assert_not_called()

    def test_migration_failure_falls_back_to_warning(self, monkeypatch, tmp_path, caplog):
        """If migration fails, should log a warning with manual instructions."""
        self._clean_env(monkeypatch)
        legacy_dir = tmp_path / "legacy"
        legacy_dir.mkdir()
        (legacy_dir / "data.bin").write_text("legacy")

        from mem0.vector_stores.configs import _migrate_legacy_data

        with patch("mem0.vector_stores.configs.Path") as mock_path_cls:
            real_legacy = Path(str(legacy_dir))

            mock_new_path = MagicMock()
            mock_new_path.exists.return_value = False
            mock_sentinel = MagicMock()
            mock_sentinel.exists.return_value = False
            mock_new_path.__truediv__ = MagicMock(return_value=mock_sentinel)

            mock_path_cls.side_effect = lambda p: real_legacy if "/tmp/" in str(p) else mock_new_path

            with patch("shutil.copytree", side_effect=PermissionError("denied")):
                with caplog.at_level(logging.WARNING, logger="mem0.vector_stores.configs"):
                    _migrate_legacy_data("qdrant", "/new/path")

        assert "denied" in caplog.text or "manually" in caplog.text.lower() or "move" in caplog.text.lower()

    def test_no_migration_when_explicit_path_provided(self, monkeypatch, caplog):
        """Should not attempt migration when user provides explicit path."""
        self._clean_env(monkeypatch)
        with caplog.at_level(logging.WARNING, logger="mem0.vector_stores.configs"):
            VectorStoreConfig(provider="qdrant", config={"path": "/my/path"})

        assert "migrat" not in caplog.text.lower()


# ---------------------------------------------------------------------------
# Cross-platform / issue #4279 scenario tests
# ---------------------------------------------------------------------------

class TestIssue4279Scenarios:
    """End-to-end tests for the specific scenarios described in issue #4279."""

    def _clean_env(self, monkeypatch):
        for var in ("MEM0_DATA_DIR", "XDG_DATA_HOME", "APPDATA"):
            monkeypatch.delenv(var, raising=False)

    def test_windows_no_tmp(self, monkeypatch):
        """Windows doesn't have /tmp — APPDATA should be used."""
        self._clean_env(monkeypatch)
        monkeypatch.setenv("APPDATA", "C:\\Users\\test\\AppData\\Roaming")
        for provider in ("qdrant", "chroma", "faiss"):
            path = get_default_vector_store_path(provider)
            assert not path.startswith("/tmp"), f"Windows path for {provider} still uses /tmp"
            assert "AppData" in path

    def test_linux_systemd_with_xdg(self, monkeypatch):
        """Linux systemd services should respect XDG_DATA_HOME."""
        self._clean_env(monkeypatch)
        monkeypatch.setenv("XDG_DATA_HOME", "/var/lib/myservice")
        path = get_default_vector_store_path("qdrant")
        assert path == "/var/lib/myservice/mem0/qdrant"

    def test_docker_with_custom_data_dir(self, monkeypatch):
        """Docker users can mount a volume and point MEM0_DATA_DIR to it."""
        self._clean_env(monkeypatch)
        monkeypatch.setenv("MEM0_DATA_DIR", "/data/mem0")
        path = get_default_vector_store_path("qdrant")
        assert path == "/data/mem0/qdrant"

    def test_macos_default_is_persistent(self, monkeypatch):
        """macOS default should be under home directory, not /tmp."""
        self._clean_env(monkeypatch)
        path = get_default_vector_store_path("qdrant")
        assert path.startswith(str(Path.home()))
        assert "/tmp" not in path

    def test_all_affected_providers_fixed(self, monkeypatch):
        """All providers with a path field (qdrant, chroma, faiss) should be fixed."""
        self._clean_env(monkeypatch)
        for provider in ("qdrant", "chroma", "faiss"):
            vc = VectorStoreConfig(provider=provider, config={})
            assert "/tmp" not in vc.config.path, (
                f"Provider '{provider}' still defaults to /tmp: {vc.config.path}"
            )
