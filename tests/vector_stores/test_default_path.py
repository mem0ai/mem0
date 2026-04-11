"""Tests for the vector store default path fix (issue #4279).

Verifies that vector store defaults use platform-appropriate persistent directories
instead of /tmp, which is ephemeral and may be inaccessible in restricted environments.
"""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mem0.vector_stores.configs import (
    VectorStoreConfig,
    _migrate_legacy_data,
    get_default_vector_store_path,
)

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
    """Tests that legacy /tmp data is automatically migrated to the new path.

    Uses the ``legacy_path`` parameter of ``_migrate_legacy_data`` so that every
    test exercises real filesystem operations (via pytest ``tmp_path``) instead of
    mocking ``Path`` and ``shutil.copytree``.  This catches real issues like
    permission errors, path resolution, and symlink handling that mocks silently
    skip over.
    """

    def test_auto_migration_copies_legacy_data(self, tmp_path, caplog):
        """When legacy dir has data and new path doesn't exist, data is copied."""
        legacy = tmp_path / "legacy_qdrant"
        legacy.mkdir()
        (legacy / "collection").mkdir()
        (legacy / "collection" / "data.bin").write_bytes(b"\x00real-vector-data")

        new = tmp_path / "new_qdrant"

        with caplog.at_level(logging.INFO, logger="mem0.vector_stores.configs"):
            _migrate_legacy_data("qdrant", str(new), legacy_path=str(legacy))

        # Data was actually copied
        assert (new / "collection" / "data.bin").exists()
        assert (new / "collection" / "data.bin").read_bytes() == b"\x00real-vector-data"
        # Sentinel was written
        assert (new / ".migration_complete").exists()
        # Legacy data is untouched (copy, not move)
        assert (legacy / "collection" / "data.bin").exists()
        assert "migrated" in caplog.text.lower()

    def test_no_migration_when_legacy_path_missing(self, tmp_path):
        """No-op when the legacy directory doesn't exist at all."""
        nonexistent = tmp_path / "does_not_exist"
        new = tmp_path / "new"

        _migrate_legacy_data("qdrant", str(new), legacy_path=str(nonexistent))

        assert not new.exists()

    def test_no_migration_when_legacy_path_empty_dir(self, tmp_path):
        """No-op when the legacy directory exists but is empty."""
        legacy = tmp_path / "empty_qdrant"
        legacy.mkdir()

        new = tmp_path / "new"

        _migrate_legacy_data("qdrant", str(new), legacy_path=str(legacy))

        assert not new.exists()

    def test_no_migration_when_legacy_path_is_symlink(self, tmp_path):
        """Refuse to migrate if legacy path is a symlink (prevents symlink attacks)."""
        real_dir = tmp_path / "real_data"
        real_dir.mkdir()
        (real_dir / "secret.key").write_text("sensitive")

        symlink = tmp_path / "symlink_qdrant"
        symlink.symlink_to(real_dir)

        new = tmp_path / "new"

        _migrate_legacy_data("qdrant", str(new), legacy_path=str(symlink))

        assert not new.exists()

    def test_no_migration_when_new_path_already_has_data(self, tmp_path, caplog):
        """Don't clobber existing data at the new path."""
        legacy = tmp_path / "legacy"
        legacy.mkdir()
        (legacy / "old.bin").write_text("legacy data")

        new = tmp_path / "new"
        new.mkdir()
        (new / "existing.bin").write_text("keep this")

        with caplog.at_level(logging.INFO, logger="mem0.vector_stores.configs"):
            _migrate_legacy_data("qdrant", str(new), legacy_path=str(legacy))

        # Existing data preserved, legacy data NOT copied
        assert (new / "existing.bin").read_text() == "keep this"
        assert not (new / "old.bin").exists()
        assert "both legacy path" in caplog.text.lower()

    def test_no_migration_when_sentinel_exists(self, tmp_path):
        """Skip migration when .migration_complete sentinel already exists."""
        legacy = tmp_path / "legacy"
        legacy.mkdir()
        (legacy / "data.bin").write_text("legacy data")

        new = tmp_path / "new"
        new.mkdir()
        (new / ".migration_complete").touch()

        _migrate_legacy_data("qdrant", str(new), legacy_path=str(legacy))

        # Legacy data was NOT copied (sentinel prevented it)
        assert not (new / "data.bin").exists()

    def test_migration_failure_falls_back_to_warning(self, tmp_path, caplog):
        """If copytree fails, log a warning with manual instructions."""
        legacy = tmp_path / "legacy"
        legacy.mkdir()
        (legacy / "data.bin").write_text("legacy data")

        new = tmp_path / "new"

        with patch("shutil.copytree", side_effect=PermissionError("denied")):
            with caplog.at_level(logging.WARNING, logger="mem0.vector_stores.configs"):
                _migrate_legacy_data("qdrant", str(new), legacy_path=str(legacy))

        # No sentinel on failure
        assert not (new / ".migration_complete").exists()
        assert "denied" in caplog.text

    def test_migration_is_idempotent(self, tmp_path):
        """Running migration twice doesn't duplicate data (sentinel prevents re-run)."""
        legacy = tmp_path / "legacy"
        legacy.mkdir()
        (legacy / "data.bin").write_text("original")

        new = tmp_path / "new"

        _migrate_legacy_data("qdrant", str(new), legacy_path=str(legacy))
        assert (new / "data.bin").read_text() == "original"

        # Modify legacy data after first migration
        (legacy / "data.bin").write_text("modified")

        # Second call is a no-op because sentinel exists
        _migrate_legacy_data("qdrant", str(new), legacy_path=str(legacy))
        assert (new / "data.bin").read_text() == "original"

    def test_migration_preserves_nested_directory_structure(self, tmp_path):
        """Deep directory trees are faithfully copied."""
        legacy = tmp_path / "legacy"
        (legacy / "collections" / "default" / "segments").mkdir(parents=True)
        (legacy / "collections" / "default" / "segments" / "index.bin").write_bytes(b"\x01\x02")
        (legacy / "meta.json").write_text('{"version": 1}')

        new = tmp_path / "new"

        _migrate_legacy_data("qdrant", str(new), legacy_path=str(legacy))

        assert (new / "meta.json").read_text() == '{"version": 1}'
        assert (new / "collections" / "default" / "segments" / "index.bin").read_bytes() == b"\x01\x02"

    def test_no_migration_when_explicit_path_provided(self, monkeypatch, caplog):
        """VectorStoreConfig with explicit path should not trigger migration."""
        for var in ("MEM0_DATA_DIR", "XDG_DATA_HOME", "APPDATA"):
            monkeypatch.delenv(var, raising=False)
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
