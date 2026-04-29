"""Tests for CLI telemetry — focused on security and env-var API key handling."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest

from mem0_cli.telemetry import capture_event


class TestTelemetrySecurity:
    """Security regression tests for telemetry subprocess spawning.

    Regression: API keys were previously passed via sys.argv (visible in ps/cmdline).
    Fix: API key is now passed via MEM0_API_KEY environment variable.
    See: https://github.com/mem0ai/mem0/issues/4862
    """

    @patch("mem0_cli.telemetry.subprocess.Popen")
    @patch("mem0_cli.telemetry.load_config")
    @patch("mem0_cli.telemetry.is_agent_mode")
    @patch("mem0_cli.telemetry._get_distinct_id")
    def test_api_key_not_in_subprocess_argv(
        self, mock_get_distinct, mock_agent_mode, mock_load_config, mock_popen
    ) -> None:
        """Verify the API key is never included in the subprocess command-line args."""
        mock_get_distinct.return_value = "test@example.com"
        mock_agent_mode.return_value = False
        mock_config = _make_config(api_key="sk-verysecret123")
        mock_load_config.return_value = mock_config

        capture_event("test_event", properties={"foo": "bar"})

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args

        argv_list = call_args[0][0]  # positional args to Popen
        # The JSON context is the last argv element
        context_json = argv_list[-1]
        context = json.loads(context_json)

        # API key must NOT be in the context dict (was previously in mem0_api_key field)
        assert "mem0_api_key" not in context, "API key leaked into subprocess argv"
        assert "sk-verysecret123" not in context_json, "API key leaked into subprocess argv"

    @patch("mem0_cli.telemetry.subprocess.Popen")
    @patch("mem0_cli.telemetry.load_config")
    @patch("mem0_cli.telemetry.is_agent_mode")
    @patch("mem0_cli.telemetry._get_distinct_id")
    def test_api_key_passed_via_env_var(
        self, mock_get_distinct, mock_agent_mode, mock_load_config, mock_popen
    ) -> None:
        """Verify the API key is passed via MEM0_API_KEY environment variable."""
        mock_get_distinct.return_value = "test@example.com"
        mock_agent_mode.return_value = False
        mock_config = _make_config(api_key="sk-testkey456")
        mock_load_config.return_value = mock_config

        capture_event("test_event")

        mock_popen.assert_called_once()
        call_kwargs = call_args_from_mock(call_args=mock_popen.call_args)

        env = call_kwargs.get("env") or os.environ
        assert "MEM0_API_KEY" in env, "MEM0_API_KEY not set in subprocess env"
        assert env["MEM0_API_KEY"] == "sk-testkey456"

    @patch("mem0_cli.telemetry.subprocess.Popen")
    @patch("mem0_cli.telemetry.load_config")
    @patch("mem0_cli.telemetry.is_agent_mode")
    @patch("mem0_cli.telemetry._get_distinct_id")
    def test_no_api_key_means_no_env_var(
        self, mock_get_distinct, mock_agent_mode, mock_load_config, mock_popen
    ) -> None:
        """When no API key is configured, MEM0_API_KEY should not be set."""
        mock_get_distinct.return_value = "anon-user"
        mock_agent_mode.return_value = False
        mock_config = _make_config(api_key="")
        mock_load_config.return_value = mock_config

        capture_event("test_event")

        mock_popen.assert_called_once()
        call_kwargs = call_args_from_mock(call_args=mock_popen.call_args)
        env = call_kwargs.get("env")
        if env is not None:
            assert "MEM0_API_KEY" not in env


# ── Helpers ────────────────────────────────────────────────────────────────────


def call_args_from_mock(call_args) -> dict:
    """Extract kwargs from a unittest.mock call args object."""
    # call_args[1] is kwargs dict
    return call_args[1] if len(call_args) > 1 else {}


def _make_config(api_key: str = "", base_url: str = "https://api.mem0.ai"):
    """Return a minimal mock config object matching the real config structure."""

    class PlatformCfg:
        def __init__(self):
            self.api_key = api_key
            self.base_url = base_url
            self.user_email = ""

    class TelemetryCfg:
        def __init__(self):
            self.anonymous_id = "test-anon-123"

    class Config:
        def __init__(self):
            self.platform = PlatformCfg()
            self.telemetry = TelemetryCfg()

    return Config()
