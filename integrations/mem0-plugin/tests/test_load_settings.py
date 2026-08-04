"""Tests for scripts/load_settings.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest


@pytest.fixture()
def settings(tmp_path, monkeypatch):
    import load_settings

    path = tmp_path / ".mem0" / "settings.json"
    monkeypatch.setattr(load_settings, "SETTINGS_PATH", path)
    return load_settings


def test_creates_file_when_absent(settings):
    assert settings.create_default_settings() is True
    assert settings.SETTINGS_PATH.exists()
    assert json.loads(settings.SETTINGS_PATH.read_text()) == settings.DEFAULTS


def test_does_not_recreate_or_overwrite_existing(settings):
    settings.SETTINGS_PATH.parent.mkdir(parents=True)
    settings.SETTINGS_PATH.write_text('{"search_limit": 42}')

    assert settings.create_default_settings() is False
    assert json.loads(settings.SETTINGS_PATH.read_text()) == {"search_limit": 42}


def test_user_values_override_defaults(settings):
    settings.SETTINGS_PATH.parent.mkdir(parents=True)
    settings.SETTINGS_PATH.write_text('{"search_limit": 3, "auto_save": false}')

    loaded = settings.load_settings()
    assert loaded["search_limit"] == 3
    assert loaded["auto_save"] is False
    assert loaded["global_search"] == settings.DEFAULTS["global_search"]


def test_unknown_keys_are_dropped_but_reported(settings):
    settings.SETTINGS_PATH.parent.mkdir(parents=True)
    settings.SETTINGS_PATH.write_text('{"skip_tools": ["Read"], "output_style": "compact"}')

    assert "skip_tools" not in settings.load_settings()
    assert settings.unknown_keys() == ["output_style", "skip_tools"]


def test_unknown_keys_empty_for_clean_file(settings):
    settings.create_default_settings()
    assert settings.unknown_keys() == []


@pytest.mark.parametrize("body", ["{not json", '["a", "list"]'])
def test_malformed_file_falls_back_to_defaults(settings, body):
    settings.SETTINGS_PATH.parent.mkdir(parents=True)
    settings.SETTINGS_PATH.write_text(body)

    assert settings.load_settings() == settings.DEFAULTS
    assert settings.unknown_keys() == []


def test_init_announces_creation_only_once(_isolated_home):
    import load_settings

    home = _isolated_home

    def run_init():
        return subprocess.run(
            [sys.executable, load_settings.__file__, "init"],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "HOME": str(home)},
        ).stdout

    first = run_init()
    second = run_init()

    assert "Created" in first
    assert "Created" not in second
