"""Tests for branding and output helpers."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from mem0_cli.branding import print_banner, print_error, print_info, print_success, print_warning


def _make_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    return Console(file=buf, force_terminal=False, no_color=True, width=80), buf


class TestBranding:
    def test_print_banner(self):
        console, buf = _make_console()
        print_banner(console)
        output = buf.getvalue()
        # Banner contains the mem0 ASCII art and tagline
        assert "Memory Layer" in output or "mem" in output.lower()

    def test_print_success(self):
        console, buf = _make_console()
        print_success(console, "It worked!")
        output = buf.getvalue()
        assert "It worked!" in output

    def test_print_error(self):
        console, buf = _make_console()
        print_error(console, "Something failed", hint="Try this fix")
        output = buf.getvalue()
        assert "Something failed" in output
        assert "Try this fix" in output

    def test_print_error_no_hint(self):
        console, buf = _make_console()
        print_error(console, "Failed")
        output = buf.getvalue()
        assert "Failed" in output

    def test_print_warning(self):
        console, buf = _make_console()
        print_warning(console, "Watch out")
        output = buf.getvalue()
        assert "Watch out" in output

    def test_print_info(self):
        console, buf = _make_console()
        print_info(console, "FYI")
        output = buf.getvalue()
        assert "FYI" in output
