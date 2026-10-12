"""Tests for configuration management."""

from __future__ import annotations

import contextlib
import os

from mem0_cli.config import (
    Mem0Config,
    get_nested_value,
    load_config,
    redact_key,
    save_config,
    set_nested_value,
)


class TestRedactKey:
    def test_empty_key(self):
        assert redact_key("") == "(not set)"

    def test_short_key(self):
        assert redact_key("abc") == "ab***"

    def test_normal_key(self):
        result = redact_key("m0-abcdefgh12345678")
        assert result == "m0-a...5678"
        assert "abcdefgh" not in result

    def test_exact_8_chars(self):
        # 8 chars is <= 8, so it gets the short redaction
        assert redact_key("12345678") == "12***"


class TestConfig:
    def test_default_config(self):
        config = Mem0Config()
        assert config.platform.base_url == "https://api.mem0.ai"
        assert config.platform.api_key == ""

    def test_save_and_load(self, isolate_config):
        config = Mem0Config()
        config.platform.api_key = "m0-test-key"

        save_config(config)

        loaded = load_config()
        assert loaded.platform.api_key == "m0-test-key"

    def test_env_var_override(self, isolate_config, monkeypatch):
        config = Mem0Config()
        config.platform.api_key = "file-key"
        save_config(config)

        monkeypatch.setenv("MEM0_API_KEY", "env-key")
        loaded = load_config()
        assert loaded.platform.api_key == "env-key"

    def test_load_nonexistent_config(self, isolate_config):
        config = load_config()
        assert config.platform.api_key == ""

    def test_config_file_permissions(self, isolate_config):
        config = Mem0Config()
        config.platform.api_key = "secret"
        save_config(config)

        from mem0_cli.config import CONFIG_FILE

        mode = os.stat(CONFIG_FILE).st_mode & 0o777
        if os.name != "nt":
            assert mode == 0o600

    def test_defaults_save_and_load(self, isolate_config):
        config = Mem0Config()
        config.defaults.user_id = "alice"
        config.defaults.agent_id = "support-bot"
        config.defaults.app_id = "my-app"
        config.defaults.run_id = "run-001"

        save_config(config)
        loaded = load_config()

        assert loaded.defaults.user_id == "alice"
        assert loaded.defaults.agent_id == "support-bot"
        assert loaded.defaults.app_id == "my-app"
        assert loaded.defaults.run_id == "run-001"

    def test_defaults_env_var_override(self, isolate_config, monkeypatch):
        config = Mem0Config()
        config.defaults.user_id = "file-user"
        save_config(config)

        monkeypatch.setenv("MEM0_USER_ID", "env-user")
        monkeypatch.setenv("MEM0_AGENT_ID", "env-agent")
        loaded = load_config()
        assert loaded.defaults.user_id == "env-user"
        assert loaded.defaults.agent_id == "env-agent"

    def test_backward_compat_no_defaults_key(self, isolate_config):
        """Old config files without 'defaults' key should load fine."""
        import json

        from mem0_cli.config import CONFIG_FILE, ensure_config_dir

        ensure_config_dir()
        # Write a config without the "defaults" key
        data = {
            "version": 1,
            "platform": {"api_key": "m0-test", "base_url": "https://api.mem0.ai"},
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f)

        loaded = load_config()
        assert loaded.platform.api_key == "m0-test"
        assert loaded.defaults.user_id == ""
        assert loaded.defaults.agent_id == ""

    def test_load_malformed_json_falls_back_to_defaults(self, isolate_config):
        """A truncated/invalid JSON file must not crash the CLI."""
        from mem0_cli.config import CONFIG_FILE, ensure_config_dir

        ensure_config_dir()
        CONFIG_FILE.write_text('{"version": 1, "platform": {')

        loaded = load_config()
        assert loaded.platform.api_key == ""
        assert loaded.version == 1

    def test_load_non_dict_json_falls_back_to_defaults(self, isolate_config):
        """Valid JSON that isn't an object (e.g. a list) must not crash the CLI."""
        from mem0_cli.config import CONFIG_FILE, ensure_config_dir

        ensure_config_dir()
        CONFIG_FILE.write_text("[1, 2, 3]")

        loaded = load_config()
        assert loaded.platform.api_key == ""
        assert loaded.version == 1

    def test_save_config_does_not_leave_tmp_file(self, isolate_config):
        """save_config() writes atomically: no leftover .json.tmp file."""
        from mem0_cli.config import CONFIG_FILE

        config = Mem0Config()
        config.platform.api_key = "m0-test"
        save_config(config)

        tmp_file = CONFIG_FILE.with_suffix(".json.tmp")
        assert not tmp_file.exists()
        assert CONFIG_FILE.exists()
        assert load_config().platform.api_key == "m0-test"

    def test_save_config_failure_does_not_corrupt_existing_file(self, isolate_config, monkeypatch):
        """An interrupted write must not truncate a previously-valid config.json."""
        config = Mem0Config()
        config.platform.api_key = "original"
        save_config(config)

        def _boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("json.dump", _boom)
        new_config = Mem0Config()
        new_config.platform.api_key = "should-not-be-written"
        with contextlib.suppress(OSError):
            save_config(new_config)

        loaded = load_config()
        assert loaded.platform.api_key == "original"

    def test_default_config_has_empty_defaults(self):
        config = Mem0Config()
        assert config.defaults.user_id == ""
        assert config.defaults.agent_id == ""
        assert config.defaults.app_id == ""
        assert config.defaults.run_id == ""


class TestNestedAccess:
    def test_get_nested_value(self):
        config = Mem0Config()
        config.platform.api_key = "test-key"
        assert get_nested_value(config, "platform.api_key") == "test-key"

    def test_get_nonexistent_key(self):
        config = Mem0Config()
        assert get_nested_value(config, "nonexistent.key") is None

    def test_set_nested_value(self):
        config = Mem0Config()
        assert set_nested_value(config, "platform.api_key", "new-key")
        assert config.platform.api_key == "new-key"

    def test_set_int_value_rejects_invalid_input(self):
        config = Mem0Config()
        assert set_nested_value(config, "version", "abc") is False
        assert config.version == 1

    def test_set_nonexistent_key(self):
        config = Mem0Config()
        assert set_nested_value(config, "nonexistent.key", "val") is False

    def test_get_defaults_user_id(self):
        config = Mem0Config()
        config.defaults.user_id = "alice"
        assert get_nested_value(config, "defaults.user_id") == "alice"

    def test_set_defaults_user_id(self):
        config = Mem0Config()
        assert set_nested_value(config, "defaults.user_id", "bob")
        assert config.defaults.user_id == "bob"


class TestResolveIds:
    def test_cli_flag_overrides_default(self):
        from mem0_cli.app import _resolve_ids

        config = Mem0Config()
        config.defaults.user_id = "default-user"
        ids = _resolve_ids(
            config,
            user_id="cli-user",
            agent_id=None,
        )
        assert ids["user_id"] == "cli-user"

    def test_default_used_when_flag_is_none(self):
        from mem0_cli.app import _resolve_ids

        config = Mem0Config()
        config.defaults.user_id = "default-user"
        config.defaults.agent_id = "default-agent"
        ids = _resolve_ids(config, user_id=None, agent_id=None)
        assert ids["user_id"] == "default-user"
        assert ids["agent_id"] == "default-agent"

    def test_none_when_neither_set(self):
        from mem0_cli.app import _resolve_ids

        config = Mem0Config()
        ids = _resolve_ids(config, user_id=None, agent_id=None)
        assert ids["user_id"] is None
        assert ids["agent_id"] is None
        assert ids["app_id"] is None
        assert ids["run_id"] is None

    def test_empty_string_treated_as_unset(self):
        from mem0_cli.app import _resolve_ids

        config = Mem0Config()
        config.defaults.user_id = ""
        ids = _resolve_ids(config, user_id=None)
        assert ids["user_id"] is None
