"""OpenTelemetry instrumentation for the mem0 open-source ``Memory`` layer.

This module emits **spans**, **metrics**, and **logs** for every public memory
operation (``add`` / ``search`` / ``get`` / ``get_all`` / ``update`` /
``delete``) following the ``memory-semconv`` v0.1.0 semantic conventions.

Design constraints (see ISI-1926):

* **Soft dependency.** ``opentelemetry-api`` is an *optional* dependency
  (``pip install mem0ai[otel]``). If it is not importable, every hook in this
  module degrades to a no-op with zero overhead and no import error — the
  instrumentation never affects the host application.
* **Additive.** This runs *alongside* the existing PostHog ``capture_event``
  telemetry; it does not replace or remove it.
* **Vendor neutral.** We read from the OTel *global* providers
  (``trace.get_tracer`` / ``metrics.get_meter`` / ``_logs.get_logger``). The
  host application configures exporters (OTLP, stdout, Jaeger, …); this library
  never installs an SDK or exporter of its own.

Cardinality note
----------------
Span attributes (including the search query, truncated) are per-operation and
are NOT aggregated, so high-cardinality values are acceptable there. **Metric
labels are deliberately restricted** to a tiny bounded set
(``operation`` / ``store_kind`` / ``sut_name`` / ``status``). The search query,
scope IDs (``user_id`` / ``agent_id`` / ``run_id``) and memory IDs must never be
promoted to metric labels — doing so would cause dimensional explosion.
"""

from __future__ import annotations

import functools
import inspect
import logging
import os
import time
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Soft import of the OpenTelemetry API. Everything below degrades to a no-op   #
# when the API is not installed.                                              #
# --------------------------------------------------------------------------- #
try:
    from opentelemetry import metrics as _otel_metrics
    from opentelemetry import trace as _otel_trace
    from opentelemetry.trace import SpanKind, Status, StatusCode

    _OTEL_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only when otel not installed
    _otel_metrics = None
    _otel_trace = None
    SpanKind = Status = StatusCode = None
    _OTEL_AVAILABLE = False

# The logs signal lives under the ``_logs`` module and its emit surface has
# shifted between releases. Import only the *API* (never the SDK) and emit
# defensively so a version bump never breaks span/metric emission.
try:  # pragma: no branch
    from opentelemetry import _logs as _otel_logs
    from opentelemetry._logs import SeverityNumber as _SeverityNumber

    _OTEL_LOGS_AVAILABLE = _OTEL_AVAILABLE
except Exception:  # pragma: no cover
    _otel_logs = None
    _SeverityNumber = None
    _OTEL_LOGS_AVAILABLE = False


# --------------------------------------------------------------------------- #
# memory-semconv v0.1.0 constants                                             #
# --------------------------------------------------------------------------- #
INSTRUMENTATION_NAME = "mem0.memory"
INSTRUMENTATION_VERSION = "0.1.0"  # memory-semconv schema version
SUT_NAME = "mem0"
SCHEMA_URL = "https://mem0.ai/schemas/memory-semconv/0.1.0"

# Span / resource attribute keys
ATTR_OPERATION = "memory.operation"
ATTR_SUT_NAME = "memory.sut.name"
ATTR_ARCHITECTURE = "memory.architecture"
ATTR_STORE_BACKEND = "memory.store_backend"
ATTR_EMBEDDING_MODEL = "memory.embedding.model"
ATTR_VECTOR_DIMS = "memory.vector.dims"
ATTR_MEMORY_ID = "memory.id"
ATTR_QUERY_LENGTH = "memory.query.length"
ATTR_QUERY_TEXT = "memory.query.text"
ATTR_RESULT_COUNT = "memory.result.count"
ATTR_TOP_SIMILARITY = "memory.top_similarity"
ATTR_HIT = "memory.hit"
ATTR_ITEM_COUNT = "memory.item.count"
ATTR_BYTES = "memory.bytes"
ATTR_INFER = "memory.infer"
# Scope IDs — span-only, never metric labels.
ATTR_SCOPE_USER = "memory.scope.user_id"
ATTR_SCOPE_AGENT = "memory.scope.agent_id"
ATTR_SCOPE_RUN = "memory.scope.run_id"

# Metric instrument names (kept identical to the memory-semconv registry so a
# single Weaver policy validates every mem-fork: mem0 / memU / mcp_server).
METRIC_OP_DURATION = "memory_operation_duration_seconds"
METRIC_RECALL_RESULTS = "memory_recall_results_count"
METRIC_RECALL_TOP_SIM = "memory_recall_top_similarity"
METRIC_ITEMS_TOTAL = "memory_items_total"
METRIC_BYTES_TOTAL = "memory_bytes_total"

# Operations that produce recall results (result-count / top-similarity metrics).
_RECALL_OPS = frozenset({"search", "get_all"})


# --------------------------------------------------------------------------- #
# Runtime configuration (all env-driven, read once at import).                #
# --------------------------------------------------------------------------- #
def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# Master switch. When the API is installed, instrumentation is on by default but
# can be force-disabled with ``MEM0_OTEL_ENABLED=false``.
_ENABLED = _OTEL_AVAILABLE and _env_flag("MEM0_OTEL_ENABLED", True)

# PII controls for the search query. The query is captured on the *span* by
# default (truncated), and can be redacted entirely for sensitive deployments.
_CAPTURE_QUERY_TEXT = _env_flag("MEM0_OTEL_CAPTURE_QUERY_TEXT", True)
try:
    _QUERY_MAX_LEN = int(os.environ.get("MEM0_OTEL_QUERY_MAX_LEN", "256"))
except (TypeError, ValueError):
    _QUERY_MAX_LEN = 256


def is_enabled() -> bool:
    """Return ``True`` when OTel instrumentation is active."""
    return _ENABLED


# --------------------------------------------------------------------------- #
# Lazy provider / instrument singletons.                                      #
# --------------------------------------------------------------------------- #
_tracer = None
_meter = None
_otel_logger = None
_instruments: Dict[str, Any] = {}


def _get_tracer():
    global _tracer
    if _tracer is None:
        _tracer = _otel_trace.get_tracer(
            INSTRUMENTATION_NAME, INSTRUMENTATION_VERSION, schema_url=SCHEMA_URL
        )
    return _tracer


def _get_meter():
    global _meter
    if _meter is None:
        _meter = _otel_metrics.get_meter(
            INSTRUMENTATION_NAME, INSTRUMENTATION_VERSION, schema_url=SCHEMA_URL
        )
    return _meter


def _get_logger():
    global _otel_logger
    if _otel_logger is None and _OTEL_LOGS_AVAILABLE:
        _otel_logger = _otel_logs.get_logger(
            INSTRUMENTATION_NAME, INSTRUMENTATION_VERSION, schema_url=SCHEMA_URL
        )
    return _otel_logger


def _get_instruments() -> Dict[str, Any]:
    """Create (once) and return the semconv metric instruments."""
    if _instruments:
        return _instruments
    meter = _get_meter()
    _instruments["op_duration"] = meter.create_histogram(
        name=METRIC_OP_DURATION,
        unit="s",
        description="Duration of a memory operation.",
    )
    _instruments["recall_results"] = meter.create_histogram(
        name=METRIC_RECALL_RESULTS,
        unit="{result}",
        description="Number of results returned by a recall operation.",
    )
    _instruments["recall_top_sim"] = meter.create_histogram(
        name=METRIC_RECALL_TOP_SIM,
        unit="1",
        description="Similarity score of the top recall result.",
    )
    _instruments["items_total"] = meter.create_counter(
        name=METRIC_ITEMS_TOTAL,
        unit="{item}",
        description="Total memory items written.",
    )
    _instruments["bytes_total"] = meter.create_counter(
        name=METRIC_BYTES_TOTAL,
        unit="By",
        description="Total bytes of memory content written.",
    )
    return _instruments


def reset_for_testing() -> None:
    """Drop cached providers/instruments so a test can swap global providers.

    Tests install fresh ``InMemory*`` providers and then call this to force the
    module to re-resolve tracer/meter/logger against them.
    """
    global _tracer, _meter, _otel_logger
    _tracer = None
    _meter = None
    _otel_logger = None
    _instruments.clear()


# --------------------------------------------------------------------------- #
# Attribute extraction helpers.                                               #
# --------------------------------------------------------------------------- #
def _truncate_query(query: str) -> str:
    if len(query) <= _QUERY_MAX_LEN:
        return query
    return query[:_QUERY_MAX_LEN] + "…"


def _resource_attrs(instance: Any) -> Dict[str, Any]:
    """Static, per-instance descriptive attributes (safe getattr chains)."""
    attrs: Dict[str, Any] = {ATTR_SUT_NAME: SUT_NAME}
    try:
        cfg = instance.config
        attrs[ATTR_STORE_BACKEND] = getattr(cfg.vector_store, "provider", None)
        attrs[ATTR_EMBEDDING_MODEL] = getattr(cfg.embedder, "provider", None)
        graph = getattr(cfg, "graph_store", None)
        graph_provider = getattr(graph, "provider", None) if graph else None
        attrs[ATTR_ARCHITECTURE] = "vector+graph" if graph_provider else "vector"
    except Exception:  # pragma: no cover - defensive
        pass
    try:
        dims = instance.embedding_model.config.embedding_dims
        if dims is not None:
            attrs[ATTR_VECTOR_DIMS] = dims
    except Exception:  # pragma: no cover - defensive
        pass
    return {k: v for k, v in attrs.items() if v is not None}


def _store_kind(instance: Any) -> str:
    try:
        return getattr(instance.config.vector_store, "provider", None) or "unknown"
    except Exception:  # pragma: no cover - defensive
        return "unknown"


def _scope_from_filters(filters: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if isinstance(filters, dict):
        for key, attr in (
            ("user_id", ATTR_SCOPE_USER),
            ("agent_id", ATTR_SCOPE_AGENT),
            ("run_id", ATTR_SCOPE_RUN),
        ):
            val = filters.get(key)
            if val is not None:
                out[attr] = str(val)
    return out


def _op_attributes(op: str, instance: Any, bound: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[str]]:
    """Return (span attributes, query-text-or-None) for a given operation call.

    ``bound`` is the ``BoundArguments.arguments`` mapping (self excluded).
    """
    attrs: Dict[str, Any] = {ATTR_OPERATION: op}
    attrs.update(_resource_attrs(instance))

    # Scope IDs from explicit kwargs (add/search) ...
    for key, attr in (
        ("user_id", ATTR_SCOPE_USER),
        ("agent_id", ATTR_SCOPE_AGENT),
        ("run_id", ATTR_SCOPE_RUN),
    ):
        val = bound.get(key)
        if val is not None:
            attrs[attr] = str(val)
    # ... and from the filters dict (get_all/search).
    attrs.update(_scope_from_filters(bound.get("filters")))

    if "memory_id" in bound and bound["memory_id"] is not None:
        attrs[ATTR_MEMORY_ID] = str(bound["memory_id"])

    if op == "add":
        infer = bound.get("infer")
        if infer is not None:
            attrs[ATTR_INFER] = bool(infer)

    query_text: Optional[str] = None
    if op == "search":
        query = bound.get("query")
        if isinstance(query, str):
            attrs[ATTR_QUERY_LENGTH] = len(query)
            if _CAPTURE_QUERY_TEXT and query:
                # PII / cardinality: truncated, span-only, never a metric label.
                query_text = _truncate_query(query)
    return attrs, query_text


def _result_metrics(op: str, result: Any) -> Dict[str, Any]:
    """Derive result-shape metrics/attributes from a method's return value."""
    out: Dict[str, Any] = {}
    try:
        if op == "search":
            items = result.get("results", []) if isinstance(result, dict) else []
            out[ATTR_RESULT_COUNT] = len(items)
            top = None
            for it in items:
                score = it.get("score") if isinstance(it, dict) else None
                if isinstance(score, (int, float)):
                    top = score if top is None else max(top, score)
            if top is not None:
                out[ATTR_TOP_SIMILARITY] = float(top)
        elif op == "get_all":
            items = result.get("results", []) if isinstance(result, dict) else []
            out[ATTR_RESULT_COUNT] = len(items)
        elif op == "get":
            out[ATTR_HIT] = result is not None
        elif op == "add":
            # ``add`` returns a list of {id, memory, event} items.
            items = result if isinstance(result, list) else []
            out[ATTR_ITEM_COUNT] = len(items)
            nbytes = 0
            for it in items:
                mem = it.get("memory") if isinstance(it, dict) else None
                if isinstance(mem, str):
                    nbytes += len(mem.encode("utf-8"))
            out[ATTR_BYTES] = nbytes
    except Exception:  # pragma: no cover - defensive
        pass
    return out


# --------------------------------------------------------------------------- #
# Metric + log emission.                                                      #
# --------------------------------------------------------------------------- #
def _record_metrics(op: str, store_kind: str, duration_s: float, status: str, derived: Dict[str, Any]) -> None:
    try:
        inst = _get_instruments()
        labels = {"operation": op, "store_kind": store_kind, "sut_name": SUT_NAME}
        inst["op_duration"].record(duration_s, {**labels, "status": status})
        if op in _RECALL_OPS and ATTR_RESULT_COUNT in derived:
            inst["recall_results"].record(derived[ATTR_RESULT_COUNT], labels)
        if op == "search" and ATTR_TOP_SIMILARITY in derived:
            inst["recall_top_sim"].record(derived[ATTR_TOP_SIMILARITY], labels)
        if op == "add":
            if derived.get(ATTR_ITEM_COUNT):
                inst["items_total"].add(derived[ATTR_ITEM_COUNT], labels)
            if derived.get(ATTR_BYTES):
                inst["bytes_total"].add(derived[ATTR_BYTES], labels)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("mem0 otel metric emission failed: %s", exc)


def _emit_log(op: str, attrs: Dict[str, Any], duration_s: float, status: str, error: Optional[str]) -> None:
    otel_logger = _get_logger()
    if otel_logger is None:
        return
    body = f"memory.{op} {status}"
    record_attrs = {**attrs, "memory.duration_s": duration_s, "memory.status": status}
    if error:
        record_attrs["exception.message"] = error
    severity = _SeverityNumber.ERROR if status == "error" else _SeverityNumber.INFO
    sev_text = "ERROR" if status == "error" else "INFO"
    # This runs while the operation span is still current, so emitting via the
    # kwargs form lets the SDK trace-correlate the record from the active
    # context automatically.
    try:
        otel_logger.emit(
            body=body,
            severity_number=severity,
            severity_text=sev_text,
            attributes=record_attrs,
        )
    except TypeError:
        # Older API: Logger.emit(record) only. Build an API LogRecord and stamp
        # trace context explicitly.
        try:
            from opentelemetry._logs import LogRecord

            span_ctx = _otel_trace.get_current_span().get_span_context()
            otel_logger.emit(
                LogRecord(
                    body=body,
                    severity_number=severity,
                    severity_text=sev_text,
                    attributes=record_attrs,
                    trace_id=span_ctx.trace_id,
                    span_id=span_ctx.span_id,
                    trace_flags=span_ctx.trace_flags,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("mem0 otel log emission failed: %s", exc)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("mem0 otel log emission failed: %s", exc)


# --------------------------------------------------------------------------- #
# The decorator.                                                              #
# --------------------------------------------------------------------------- #
def _bind_args(func: Callable, args: tuple, kwargs: dict) -> Dict[str, Any]:
    """Best-effort bind of call args to parameter names (self excluded).

    ``func`` is the *unwrapped* method, so its signature still includes ``self``.
    The wrapper strips ``self`` before calling us, so we occupy that leading
    slot with a placeholder to keep positional args aligned to their real
    parameter names.
    """
    try:
        sig = inspect.signature(func)
        bound = sig.bind_partial(None, *args, **kwargs)  # placeholder for self
        bound.apply_defaults()
        arguments = dict(bound.arguments)
        arguments.pop("self", None)
        return arguments
    except Exception:  # pragma: no cover - defensive
        return dict(kwargs)


def instrument(op: str) -> Callable:
    """Decorate a ``Memory``/``AsyncMemory`` op method with OTel instrumentation.

    Works for both sync methods and coroutine methods. When instrumentation is
    disabled (API missing or ``MEM0_OTEL_ENABLED=false``) the original function
    is returned unchanged, so there is zero call overhead.
    """

    def decorator(func: Callable) -> Callable:
        if not _OTEL_AVAILABLE:
            return func

        is_async = inspect.iscoroutinefunction(func)

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(self, *args, **kwargs):
                if not _ENABLED:
                    return await func(self, *args, **kwargs)
                bound = _bind_args(func, args, kwargs)
                attrs, query_text = _op_attributes(op, self, bound)
                tracer = _get_tracer()
                start = time.perf_counter()
                status = "ok"
                error: Optional[str] = None
                with tracer.start_as_current_span(
                    f"memory.{op}", kind=SpanKind.CLIENT, attributes=attrs
                ) as span:
                    if query_text is not None:
                        span.set_attribute(ATTR_QUERY_TEXT, query_text)
                    try:
                        result = await func(self, *args, **kwargs)
                    except Exception as exc:
                        status = "error"
                        error = f"{type(exc).__name__}: {exc}"
                        span.set_status(Status(StatusCode.ERROR, error))
                        span.record_exception(exc)
                        raise
                    finally:
                        duration = time.perf_counter() - start
                        derived = _result_metrics(op, result) if status == "ok" else {}
                        for k, v in derived.items():
                            span.set_attribute(k, v)
                        _record_metrics(op, _store_kind(self), duration, status, derived)
                        _emit_log(op, {**attrs, **derived}, duration, status, error)
                    return result

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            if not _ENABLED:
                return func(self, *args, **kwargs)
            bound = _bind_args(func, args, kwargs)
            attrs, query_text = _op_attributes(op, self, bound)
            tracer = _get_tracer()
            start = time.perf_counter()
            status = "ok"
            error: Optional[str] = None
            with tracer.start_as_current_span(
                f"memory.{op}", kind=SpanKind.CLIENT, attributes=attrs
            ) as span:
                if query_text is not None:
                    span.set_attribute(ATTR_QUERY_TEXT, query_text)
                try:
                    result = func(self, *args, **kwargs)
                except Exception as exc:
                    status = "error"
                    error = f"{type(exc).__name__}: {exc}"
                    span.set_status(Status(StatusCode.ERROR, error))
                    span.record_exception(exc)
                    raise
                finally:
                    duration = time.perf_counter() - start
                    derived = _result_metrics(op, result) if status == "ok" else {}
                    for k, v in derived.items():
                        span.set_attribute(k, v)
                    _record_metrics(op, _store_kind(self), duration, status, derived)
                    _emit_log(op, {**attrs, **derived}, duration, status, error)
                return result

        return sync_wrapper

    return decorator
