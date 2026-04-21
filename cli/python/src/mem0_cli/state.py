"""Agent mode state — set by the root callback, read by commands and branding."""

from __future__ import annotations

_agent_mode: bool = False
_current_command: str = ""


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
