"""Agent mode state — set by the root callback, read by commands and branding."""

from __future__ import annotations

_agent_mode: bool = False
_current_command: str = ""
_pending_notice: str = ""


def is_agent_mode() -> bool:
    return _agent_mode


def set_agent_mode(val: bool) -> None:
    global _agent_mode
    _agent_mode = val


def get_current_command() -> str:
    return _current_command


def set_current_command(name: str) -> None:
    global _current_command
    _current_command = name


def capture_notice(notice: str | None) -> None:
    """Stash a Mem0 backend notice for end-of-command surfacing.

    Called from the platform backend after each response so the notice can
    be printed once per command (regardless of how many sub-requests fired).
    Last-write-wins is fine — the message text is identical across requests.
    """
    global _pending_notice
    if notice:
        _pending_notice = notice


def take_notice() -> str:
    """Return and clear the pending notice."""
    global _pending_notice
    msg = _pending_notice
    _pending_notice = ""
    return msg
