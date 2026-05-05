"""Tests for PostHog identity stitching: anon → email alias on MemoryClient init.

Covers the four matrix cases (OSS-only, CLI-only, both, already-aliased) plus
failure modes: missing config, malformed JSON, read-only filesystem,
broken posthog client. Telemetry must never raise.
"""

import importlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def tmp_mem0_dir(tmp_path, monkeypatch):
    """Point the mem0 setup module at a tempdir for the duration of the test."""
    monkeypatch.setenv("MEM0_DIR", str(tmp_path))
    # Reload setup so module-level mem0_dir picks up the env var.
    import mem0.memory.setup as setup_module

    importlib.reload(setup_module)
    yield tmp_path
    # Restore default state.
    monkeypatch.delenv("MEM0_DIR", raising=False)
    importlib.reload(setup_module)


def _write_config(tmp_path: Path, payload: dict) -> Path:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(payload))
    return config_path


# ─── setup_config idempotency ────────────────────────────────────────────────


class TestSetupConfigIdempotent:
    def test_creates_config_when_missing(self, tmp_mem0_dir):
        import mem0.memory.setup as setup_module

        setup_module.setup_config()
        config = json.loads((tmp_mem0_dir / "config.json").read_text())
        assert "user_id" in config and config["user_id"]

    def test_backfills_user_id_when_only_telemetry_present(self, tmp_mem0_dir):
        import mem0.memory.setup as setup_module

        _write_config(
            tmp_mem0_dir,
            {"telemetry": {"anonymous_id": "cli-anon-abc123"}},
        )
        setup_module.setup_config()
        config = json.loads((tmp_mem0_dir / "config.json").read_text())
        assert config.get("user_id"), "user_id must be backfilled for CLI-first users"
        assert config["telemetry"]["anonymous_id"] == "cli-anon-abc123"

    def test_does_not_overwrite_existing_user_id(self, tmp_mem0_dir):
        import mem0.memory.setup as setup_module

        _write_config(tmp_mem0_dir, {"user_id": "existing-uuid"})
        setup_module.setup_config()
        config = json.loads((tmp_mem0_dir / "config.json").read_text())
        assert config["user_id"] == "existing-uuid"

    def test_handles_malformed_json(self, tmp_mem0_dir):
        import mem0.memory.setup as setup_module

        (tmp_mem0_dir / "config.json").write_text("{not json")
        setup_module.setup_config()  # must not raise
        config = json.loads((tmp_mem0_dir / "config.json").read_text())
        assert "user_id" in config


# ─── read_anon_ids ───────────────────────────────────────────────────────────


class TestReadAnonIds:
    def test_returns_oss_only(self, tmp_mem0_dir):
        import mem0.memory.setup as setup_module

        _write_config(tmp_mem0_dir, {"user_id": "oss-uuid"})
        anon = setup_module.read_anon_ids()
        assert anon == {"oss": "oss-uuid", "cli": None, "aliased_pairs": []}

    def test_returns_cli_only(self, tmp_mem0_dir):
        import mem0.memory.setup as setup_module

        _write_config(
            tmp_mem0_dir,
            {"telemetry": {"anonymous_id": "cli-anon-123"}},
        )
        anon = setup_module.read_anon_ids()
        assert anon == {"oss": None, "cli": "cli-anon-123", "aliased_pairs": []}

    def test_returns_both(self, tmp_mem0_dir):
        import mem0.memory.setup as setup_module

        _write_config(
            tmp_mem0_dir,
            {
                "user_id": "oss-uuid",
                "telemetry": {"anonymous_id": "cli-anon-123", "aliased_pairs": ["pair-marker"]},
            },
        )
        anon = setup_module.read_anon_ids()
        assert anon == {
            "oss": "oss-uuid",
            "cli": "cli-anon-123",
            "aliased_pairs": ["pair-marker"],
        }

    def test_no_config_returns_all_none(self, tmp_mem0_dir):
        import mem0.memory.setup as setup_module

        anon = setup_module.read_anon_ids()
        assert anon == {"oss": None, "cli": None, "aliased_pairs": []}

    def test_malformed_json_does_not_raise(self, tmp_mem0_dir):
        import mem0.memory.setup as setup_module

        (tmp_mem0_dir / "config.json").write_text("{not json")
        anon = setup_module.read_anon_ids()
        assert anon == {"oss": None, "cli": None, "aliased_pairs": []}


# ─── mark_aliased ────────────────────────────────────────────────────────────


class TestMarkAliased:
    def test_writes_aliased_pair_preserving_other_fields(self, tmp_mem0_dir):
        import mem0.memory.setup as setup_module

        _write_config(
            tmp_mem0_dir,
            {
                "user_id": "oss-uuid",
                "telemetry": {"anonymous_id": "cli-anon-123"},
            },
        )
        setup_module.mark_aliased("oss-uuid", "user@example.com")
        config = json.loads((tmp_mem0_dir / "config.json").read_text())
        assert config["user_id"] == "oss-uuid"
        assert config["telemetry"]["anonymous_id"] == "cli-anon-123"
        assert len(config["telemetry"]["aliased_pairs"]) == 1
        assert setup_module.is_aliased("oss-uuid", "user@example.com")

    def test_creates_telemetry_section_when_missing(self, tmp_mem0_dir):
        import mem0.memory.setup as setup_module

        _write_config(tmp_mem0_dir, {"user_id": "oss-uuid"})
        setup_module.mark_aliased("oss-uuid", "user@example.com")
        config = json.loads((tmp_mem0_dir / "config.json").read_text())
        assert len(config["telemetry"]["aliased_pairs"]) == 1

    def test_tracks_each_pair_independently(self, tmp_mem0_dir):
        import mem0.memory.setup as setup_module

        _write_config(tmp_mem0_dir, {"user_id": "oss-uuid"})
        setup_module.mark_aliased("oss-uuid", "user@example.com")
        assert setup_module.is_aliased("oss-uuid", "user@example.com")
        assert not setup_module.is_aliased("new-uuid", "user@example.com")
        assert not setup_module.is_aliased("oss-uuid", "other@example.com")


# ─── capture_identify ────────────────────────────────────────────────────────


class TestCaptureIdentify:
    def test_fires_identify_with_anon_distinct_id(self):
        import mem0.memory.telemetry as telemetry_module

        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog") as mock_posthog_cls:
                at = telemetry_module.AnonymousTelemetry()
                at.capture_identify("anon-123", "user@example.com")
                mock_ph = mock_posthog_cls.return_value
                mock_ph.capture.assert_called_once()
                _, kwargs = mock_ph.capture.call_args
                assert kwargs["distinct_id"] == "user@example.com"
                assert kwargs["event"] == "$identify"
                assert kwargs["properties"]["$anon_distinct_id"] == "anon-123"

    def test_skips_when_anon_equals_email(self):
        import mem0.memory.telemetry as telemetry_module

        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog") as mock_posthog_cls:
                at = telemetry_module.AnonymousTelemetry()
                at.capture_identify("user@example.com", "user@example.com")
                mock_posthog_cls.return_value.capture.assert_not_called()

    def test_skips_when_inputs_empty(self):
        import mem0.memory.telemetry as telemetry_module

        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog") as mock_posthog_cls:
                at = telemetry_module.AnonymousTelemetry()
                at.capture_identify("", "user@example.com")
                at.capture_identify("anon-123", "")
                mock_posthog_cls.return_value.capture.assert_not_called()

    def test_noop_when_telemetry_disabled(self):
        import mem0.memory.telemetry as telemetry_module

        with patch.object(telemetry_module, "MEM0_TELEMETRY", False):
            at = telemetry_module.AnonymousTelemetry()
            at.capture_identify("anon-123", "user@example.com")  # must not raise
            assert at.posthog is None

    def test_does_not_raise_on_posthog_error(self):
        import mem0.memory.telemetry as telemetry_module

        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog") as mock_posthog_cls:
                mock_posthog_cls.return_value.capture.side_effect = RuntimeError("boom")
                at = telemetry_module.AnonymousTelemetry()
                at.capture_identify("anon-123", "user@example.com")  # must not raise

    def test_identify_is_in_lifecycle_events(self):
        """$identify must bypass the 90% sampling drop."""
        import mem0.memory.telemetry as telemetry_module

        assert "$identify" in telemetry_module._LIFECYCLE_EVENTS


# ─── _maybe_alias_anon_to_email integration ──────────────────────────────────


class TestMaybeAliasAnonToEmail:
    """Test the alias helper in isolation by mocking out the config readers
    and the telemetry client, since module-level setup_config() side effects
    make end-to-end fixturing awkward."""

    def test_fires_identify_for_oss_uuid(self):
        from mem0.client import main as client_main

        with (
            patch.object(
                client_main,
                "read_anon_ids",
                return_value={"oss": "oss-uuid", "cli": None, "aliased_pairs": []},
            ),
            patch.object(client_main, "is_aliased", return_value=False),
            patch.object(client_main, "mark_aliased") as mark,
            patch.object(client_main, "client_telemetry") as telemetry,
        ):
            telemetry.capture_identify.return_value = True
            client_main._maybe_alias_anon_to_email("user@example.com")
            telemetry.capture_identify.assert_called_once_with("oss-uuid", "user@example.com")
            mark.assert_called_once_with("oss-uuid", "user@example.com")

    def test_fires_identify_for_cli_anon(self):
        from mem0.client import main as client_main

        with (
            patch.object(
                client_main,
                "read_anon_ids",
                return_value={"oss": None, "cli": "cli-anon-xyz", "aliased_pairs": []},
            ),
            patch.object(client_main, "is_aliased", return_value=False),
            patch.object(client_main, "mark_aliased"),
            patch.object(client_main, "client_telemetry") as telemetry,
        ):
            telemetry.capture_identify.return_value = True
            client_main._maybe_alias_anon_to_email("user@example.com")
            telemetry.capture_identify.assert_called_once_with("cli-anon-xyz", "user@example.com")

    def test_fires_identify_for_both_anon_ids(self):
        from mem0.client import main as client_main

        with (
            patch.object(
                client_main,
                "read_anon_ids",
                return_value={"oss": "oss-uuid", "cli": "cli-anon", "aliased_pairs": []},
            ),
            patch.object(client_main, "is_aliased", return_value=False),
            patch.object(client_main, "mark_aliased"),
            patch.object(client_main, "client_telemetry") as telemetry,
        ):
            telemetry.capture_identify.return_value = True
            client_main._maybe_alias_anon_to_email("user@example.com")
            assert telemetry.capture_identify.call_count == 2
            calls = {c.args for c in telemetry.capture_identify.call_args_list}
            assert ("oss-uuid", "user@example.com") in calls
            assert ("cli-anon", "user@example.com") in calls

    def test_skips_when_pair_already_aliased(self):
        from mem0.client import main as client_main

        with (
            patch.object(
                client_main,
                "read_anon_ids",
                return_value={"oss": "oss-uuid", "cli": None, "aliased_pairs": ["pair-marker"]},
            ),
            patch.object(client_main, "is_aliased", return_value=True),
            patch.object(client_main, "mark_aliased") as mark,
            patch.object(client_main, "client_telemetry") as telemetry,
        ):
            client_main._maybe_alias_anon_to_email("user@example.com")
            telemetry.capture_identify.assert_not_called()
            mark.assert_not_called()

    def test_skips_when_email_invalid(self):
        from mem0.client import main as client_main

        with patch.object(client_main, "client_telemetry") as telemetry:
            client_main._maybe_alias_anon_to_email(None)
            client_main._maybe_alias_anon_to_email("")
            client_main._maybe_alias_anon_to_email("not-an-email")
            telemetry.capture_identify.assert_not_called()

    def test_skips_when_telemetry_disabled(self):
        """When client_telemetry.posthog is None (MEM0_TELEMETRY=false), do nothing —
        no fs read, no fs write, no event. Re-enabling telemetry later must still alias."""
        from mem0.client import main as client_main

        disabled = MagicMock()
        disabled.posthog = None
        with (
            patch.object(client_main, "client_telemetry", disabled),
            patch.object(client_main, "read_anon_ids") as read,
            patch.object(client_main, "mark_aliased") as mark,
        ):
            client_main._maybe_alias_anon_to_email("user@example.com")
            read.assert_not_called()
            mark.assert_not_called()
            disabled.capture_identify.assert_not_called()

    def test_does_not_raise_on_telemetry_failure(self):
        from mem0.client import main as client_main

        mock_telemetry = MagicMock()
        mock_telemetry.capture_identify.side_effect = RuntimeError("boom")
        with (
            patch.object(
                client_main,
                "read_anon_ids",
                return_value={"oss": "oss-uuid", "cli": None, "aliased_pairs": []},
            ),
            patch.object(client_main, "is_aliased", return_value=False),
            patch.object(client_main, "mark_aliased") as mark,
            patch.object(client_main, "client_telemetry", mock_telemetry),
        ):
            client_main._maybe_alias_anon_to_email("user@example.com")  # must not raise
            mark.assert_not_called()

    def test_skips_anon_id_equal_to_email(self):
        """Defensive: if the anon_id somehow already is the email, don't self-alias."""
        from mem0.client import main as client_main

        with (
            patch.object(
                client_main,
                "read_anon_ids",
                return_value={"oss": "user@example.com", "cli": None, "aliased_pairs": []},
            ),
            patch.object(client_main, "is_aliased", return_value=False),
            patch.object(client_main, "mark_aliased"),
            patch.object(client_main, "client_telemetry") as telemetry,
        ):
            client_main._maybe_alias_anon_to_email("user@example.com")
            telemetry.capture_identify.assert_not_called()

    def test_does_not_raise_on_read_failure(self):
        """If read_anon_ids itself raises (e.g. IO error), helper must swallow it."""
        from mem0.client import main as client_main

        with (
            patch.object(client_main, "read_anon_ids", side_effect=OSError("fs broken")),
            patch.object(client_main, "client_telemetry") as telemetry,
        ):
            client_main._maybe_alias_anon_to_email("user@example.com")  # must not raise
            telemetry.capture_identify.assert_not_called()


# ─── End-to-end idempotency through real config ──────────────────────────────


class TestEndToEndIdempotency:
    """Verify the real config flow: two consecutive _maybe_alias_anon_to_email
    calls fire $identify exactly once thanks to the persisted pair marker."""

    def test_second_call_is_noop_after_pair_marker_persisted(self, tmp_mem0_dir):
        # Pre-populate config with an OSS user_id only.
        _write_config(tmp_mem0_dir, {"user_id": "oss-uuid"})
        # Reload setup so it uses the tempdir, then reload client.main so it
        # picks up the freshly-loaded read_anon_ids/mark_aliased bindings.
        import mem0.memory.setup as setup_module

        importlib.reload(setup_module)
        from mem0.client import main as client_main

        importlib.reload(client_main)

        with patch.object(client_main, "client_telemetry") as telemetry:
            telemetry.capture_identify.return_value = True
            client_main._maybe_alias_anon_to_email("user@example.com")
            first_call_count = telemetry.capture_identify.call_count
            assert first_call_count >= 1

            # Second call should hit the aliased_pairs short-circuit.
            client_main._maybe_alias_anon_to_email("user@example.com")
            assert telemetry.capture_identify.call_count == first_call_count

        config = json.loads((tmp_mem0_dir / "config.json").read_text())
        assert len(config["telemetry"]["aliased_pairs"]) == 1
