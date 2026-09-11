"""Optional OpenTelemetry tracing for memory operations.

This module is a thin, dependency-optional layer. It emits spans for the
public ``add`` and ``search`` operations (following the GenAI memory
semantic conventions) plus internal child spans for the LLM-extraction,
embedding and vector-store phases underneath them.

Nothing here changes behavior unless the caller has both installed
``opentelemetry-api`` (the ``otel`` optional dependency) and configured a
``TracerProvider``. When OpenTelemetry is not importable, every helper
degrades to a no-op with negligible overhead, so the hot path is unchanged
for the default install.

Memory content (the query text and the stored/retrieved records) is
sensitive and is only recorded when the caller opts in via
``OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true``; ids and counts
are always safe to record.
"""

from __future__ import annotations

import functools
import importlib.metadata
import inspect
import json
import os
from contextlib import contextmanager

try:
    from opentelemetry import trace
    from opentelemetry.trace import SpanKind

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when the extra is absent
    _OTEL_AVAILABLE = False


# --- Semantic-convention attribute keys (gen_ai.memory.*, development stability) ---
# Source: open-telemetry/semantic-conventions-genai, `gen_ai.memory.client` span.
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_MEMORY_RECORD_COUNT = "gen_ai.memory.record.count"
GEN_AI_MEMORY_QUERY_TEXT = "gen_ai.memory.query.text"
GEN_AI_MEMORY_RECORDS = "gen_ai.memory.records"
ERROR_TYPE = "error.type"

# `gen_ai.operation.name` enum values that describe mem0's public operations.
# `add` may create/update/consolidate records (the LLM decides), which is the
# spec's definition of `upsert_memory`; `search` maps to `search_memory`.
OP_ADD = "upsert_memory"
OP_SEARCH = "search_memory"

# Standard GenAI content-capture opt-in. Off unless explicitly set to "true".
CONTENT_CAPTURE_ENV = "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"

_INSTRUMENTING_MODULE = "mem0"


class _NoopSpan:
    """Stand-in returned when OpenTelemetry is not installed."""

    def is_recording(self):
        return False

    def set_attribute(self, *args, **kwargs):
        return None

    def set_status(self, *args, **kwargs):
        return None

    def record_exception(self, *args, **kwargs):
        return None


_NOOP_SPAN = _NoopSpan()


def _mem0_version():
    try:
        return importlib.metadata.version("mem0ai")
    except Exception:  # pragma: no cover - version metadata should always resolve
        return ""


def _get_tracer():
    # Cheap: the provider caches tracers per (name, version), and returns a
    # proxy that resolves lazily once a real TracerProvider is configured.
    return trace.get_tracer(_INSTRUMENTING_MODULE, _mem0_version())


def is_content_capture_enabled():
    """True only when the operator opts in to capturing memory content."""
    return os.environ.get(CONTENT_CAPTURE_ENV, "false").strip().lower() == "true"


def _is_recording(span):
    return bool(span) and span.is_recording()


def current_span():
    """The active span, or a no-op stand-in when tracing is unavailable."""
    if not _OTEL_AVAILABLE:
        return _NOOP_SPAN
    return trace.get_current_span()


def trace_memory_operation(operation_name):
    """Decorate a public memory method with a ``gen_ai.memory.client`` span.

    The wrapped method's body runs inside the span, so any child spans it
    opens (via :func:`memory_phase_span`) nest underneath automatically.
    Async methods are detected and wrapped with an async wrapper. When
    OpenTelemetry is absent the method is returned unchanged.
    """

    def decorator(func):
        if not _OTEL_AVAILABLE:
            return func

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                with _get_tracer().start_as_current_span(operation_name, kind=SpanKind.CLIENT) as span:
                    if span.is_recording():
                        span.set_attribute(GEN_AI_OPERATION_NAME, operation_name)
                    try:
                        return await func(*args, **kwargs)
                    except BaseException as exc:
                        if span.is_recording():
                            span.set_attribute(ERROR_TYPE, type(exc).__qualname__)
                        raise

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            with _get_tracer().start_as_current_span(operation_name, kind=SpanKind.CLIENT) as span:
                if span.is_recording():
                    span.set_attribute(GEN_AI_OPERATION_NAME, operation_name)
                try:
                    return func(*args, **kwargs)
                except BaseException as exc:
                    if span.is_recording():
                        span.set_attribute(ERROR_TYPE, type(exc).__qualname__)
                    raise

        return sync_wrapper

    return decorator


@contextmanager
def memory_phase_span(name):
    """Open an internal child span around one phase of an operation.

    No-op (yields a stand-in) when OpenTelemetry is not installed.
    """
    if not _OTEL_AVAILABLE:
        yield _NOOP_SPAN
        return
    with _get_tracer().start_as_current_span(name, kind=SpanKind.INTERNAL) as span:
        try:
            yield span
        except BaseException as exc:
            if span.is_recording():
                span.set_attribute(ERROR_TYPE, type(exc).__qualname__)
            raise


def _encode_records(records):
    try:
        return json.dumps(records, default=str, ensure_ascii=False)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return "[]"


def annotate_operation(span, *, record_count=None, query_text=None, records_factory=None):
    """Attach result attributes to an operation span.

    ``record_count`` (a safe count) is always recorded. ``query_text`` and
    the records payload are sensitive and only recorded when content capture
    is opted in; ``records_factory`` is a zero-arg callable so the payload is
    only built when it will actually be recorded.
    """
    if not _is_recording(span):
        return
    if record_count is not None:
        span.set_attribute(GEN_AI_MEMORY_RECORD_COUNT, record_count)
    if is_content_capture_enabled():
        if query_text is not None:
            span.set_attribute(GEN_AI_MEMORY_QUERY_TEXT, query_text)
        if records_factory is not None:
            span.set_attribute(GEN_AI_MEMORY_RECORDS, _encode_records(records_factory()))
