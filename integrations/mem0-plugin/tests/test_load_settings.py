"""Tests for load_settings.py — plugin settings loader."""

from __future__ import annotations

import json


def test_defaults_include_prefetch_top_k():
    """Regression for #6135: prefetch_top_k is a first-class setting."""
    from load_settings import DEFAULTS

    assert DEFAULTS["prefetch_top_k"] == 5


def test_user_settings_override_prefetch_top_k(tmp_path, monkeypatch):
    import load_settings

    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"prefetch_top_k": 20}))
    monkeypatch.setattr(load_settings, "SETTINGS_PATH", settings_file)

    assert load_settings.load_settings()["prefetch_top_k"] == 20


def test_unknown_keys_ignored_and_missing_file_falls_back(tmp_path, monkeypatch):
    import load_settings

    monkeypatch.setattr(load_settings, "SETTINGS_PATH", tmp_path / "missing.json")
    settings = load_settings.load_settings()
    assert settings == load_settings.DEFAULTS

    bad_file = tmp_path / "settings.json"
    bad_file.write_text(json.dumps({"prefetch_top_k": 7, "not_a_setting": True}))
    monkeypatch.setattr(load_settings, "SETTINGS_PATH", bad_file)
    settings = load_settings.load_settings()
    assert settings["prefetch_top_k"] == 7
    assert "not_a_setting" not in settings
