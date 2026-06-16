"""Centralized structured logging for Mem0 operational analysis.

Provides leveled logging with contextual metadata (operation, user_id, agent_id,
run_id, timing) across the entire memory pipeline.

Usage:
    from mem0.utils.logger import op_logger

    logger = op_logger(__name__)
    logger.info("operation_start", operation="add", user_id="u1")
    logger.success("operation_complete", duration_ms=123)
"""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from typing import Literal

# ── Operation ID context ──────────────────────────────────────────────────

_op_ctx: dict[str, Any] = {}


def set_op_ctx(**kwargs: str) -> None:
    """Set contextual metadata that flows through all log calls in this operation."""
    _op_ctx.update(kwargs)


def clear_op_ctx() -> None:
    """Clear the operation context (call at the end of each top-level operation)."""
    _op_ctx.clear()


@contextmanager
def op_context(**kwargs: str) -> Any:
    """Context manager that sets operation context and auto-clears on exit."""
    set_op_ctx(**kwargs)
    try:
        yield
    finally:
        clear_op_ctx()


# ── Timer helper ──────────────────────────────────────────────────────────


class _Timer:
    """Simple elapsed-time tracker used by ``operation_timer``."""

    def __init__(self) -> None:
        self._start: float = 0.0
        self._last: float = 0.0

    def reset(self) -> None:
        self._start = time.perf_counter()
        self._last = self._start

    @property
    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000

    @property
    def since_last_ms(self) -> float:
        now = time.perf_counter()
        delta = (now - self._last) * 1000
        self._last = now
        return delta


# ── Operation logger wrapper ─────────────────────────────────────────────


class OpLogger:
    """Thin wrapper around a stdlib logger that enriches every call with
    operation context (operation name, user_id, agent_id, run_id, op_id)
    and provides convenience methods for common operational patterns."""

    __slots__ = ("_logger", "operation")

    def __init__(self, name: str, operation: str = "") -> None:
        self._logger = logging.getLogger(name)
        self.operation = operation

    # -- fluent helpers --

    def _meta(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        """Merge global context with method-level extra."""
        merged = {
            **_op_ctx,
            "op_id": _op_ctx.get("op_id", str(uuid.uuid4())[:8]),
        }
        if extra:
            merged.update(extra)
        # Only include keys that have values
        return {k: v for k, v in merged.items() if v is not None}

    def debug(self, msg: str, **extra: Any) -> None:
        self._logger.debug(msg, extra=self._meta(extra))

    def info(self, msg: str, **extra: Any) -> None:
        self._logger.info(msg, extra=self._meta(extra))

    def warning(self, msg: str, **extra: Any) -> None:
        self._logger.warning(msg, extra=self._meta(extra))

    def error(self, msg: str, **extra: Any) -> None:
        self._logger.error(msg, extra=self._meta(extra))

    def success(self, msg: str = "", **extra: Any) -> None:
        """Log a success message with level INFO."""
        self.info(msg or f"Operation completed", **extra)

    # -- high-level operation logging --

    def log_start(self, msg: str = "Operation started", **extra: Any) -> None:
        """Log operation start with timer reset."""
        extra.setdefault("phase", "start")
        extra.setdefault("status", "started")
        self.info(msg, **extra)

    def log_end(self, msg: str = "Operation completed", **extra: Any) -> None:
        """Log operation end with elapsed time."""
        extra.setdefault("phase", "end")
        extra.setdefault("status", "completed")
        self.success(msg, **extra)

    def log_phase(
        self,
        phase: int | str,
        msg: str,
        **extra: Any,
    ) -> None:
        """Log a phase entry (used in the add() pipeline)."""
        extra.setdefault("phase", str(phase))
        extra["status"] = "phase_start"
        self.info(msg, **extra)

    def log_phase_end(
        self,
        phase: int | str,
        msg: str,
        elapsed_ms: float,
        **extra: Any,
    ) -> None:
        """Log a phase exit with elapsed time."""
        extra.setdefault("phase", str(phase))
        extra["status"] = "phase_end"
        extra["elapsed_ms"] = round(elapsed_ms, 2)
        self.info(msg, **extra)

    # -- timer context manager --

    def timer(self) -> _Timer:
        t = _Timer()
        t.reset()
        return t


# ── Factory function ─────────────────────────────────────────────────────


def op_logger(name: str, operation: str = "") -> OpLogger:
    """Create an operation logger for the given module name.

    Args:
        name: Typically ``__name__`` of the caller module.
        operation: Short operation name (e.g. "add", "search", "init").

    Returns:
        An OpLogger instance.
    """
    return OpLogger(name, operation)
