"""Structured logging context (request_id / job_id correlation)."""

from __future__ import annotations

import contextvars
import logging
import uuid

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)
job_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("job_id", default="")


class StructuredContextFilter(logging.Filter):
    """Inject ``request_id`` and ``job_id`` into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or "-"
        record.job_id = job_id_var.get() or "-"
        record.trace_id = _safe_trace_id()
        return True


def _safe_trace_id() -> str:
    """``trace_id`` do span OTel corrente para pivô log↔trace (``-`` se ausente)."""
    try:
        from app.utils.tracing import current_trace_id

        return current_trace_id() or "-"
    except Exception:  # noqa: BLE001
        return "-"


def install_structured_logging() -> None:
    """Attach the context filter to the root logger once."""
    root = logging.getLogger()
    if any(isinstance(f, StructuredContextFilter) for f in root.filters):
        return
    root.addFilter(StructuredContextFilter())
    for handler in root.handlers:
        handler.addFilter(StructuredContextFilter())


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]
