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

import contextlib
import contextvars
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
ATTR_EVENT = "memory.event"
# Scope IDs — span-only, never metric labels.
ATTR_SCOPE_USER = "memory.scope.user_id"
ATTR_SCOPE_AGENT = "memory.scope.agent_id"
ATTR_SCOPE_RUN = "memory.scope.run_id"

# The agent-memory identity of the operation currently in flight. Set by the
# ``@instrument`` wrapper and read by the internal child-span wrapper so *every*
# span in the trace (op + embedding/vector-store/LLM children) carries the
# dedicated agent-memory attributes (operation + sut.name + scope IDs), not just
# the top-level op span.
_active_op_attrs: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar(
    "mem0_otel_active_op_attrs", default=None
)
# Internal sub-operation (child span) attributes — these produce the *end-to-end*
# trace tree beneath a ``memory.<op>`` span (embedding → vector store → LLM).
ATTR_EMBEDDING_ACTION = "memory.embedding.action"
ATTR_DB_OPERATION = "memory.db.operation"
ATTR_LLM_MODEL = "memory.llm.model"

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
        _tracer = _otel_trace.get_tracer(INSTRUMENTATION_NAME, INSTRUMENTATION_VERSION, schema_url=SCHEMA_URL)
    return _tracer


def _get_meter():
    global _meter
    if _meter is None:
        _meter = _otel_metrics.get_meter(INSTRUMENTATION_NAME, INSTRUMENTATION_VERSION, schema_url=SCHEMA_URL)
    return _meter


def _get_logger():
    global _otel_logger
    if _otel_logger is None and _OTEL_LOGS_AVAILABLE:
        _otel_logger = _otel_logs.get_logger(INSTRUMENTATION_NAME, INSTRUMENTATION_VERSION, schema_url=SCHEMA_URL)
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
            events = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                mem = it.get("memory")
                if isinstance(mem, str):
                    nbytes += len(mem.encode("utf-8"))
                ev = it.get("event")
                if isinstance(ev, str) and ev not in events:
                    events.append(ev)
            out[ATTR_BYTES] = nbytes
            if events:
                # The memory mutations the agent produced this call (ADD/UPDATE/DELETE).
                out[ATTR_EVENT] = ",".join(events)
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


def _agent_memory_ctx(attrs: Dict[str, Any]) -> Dict[str, Any]:
    """The subset of op attributes that identify the agent-memory operation.

    Propagated onto every child span (embedding / vector store / LLM) so no span
    in the trace is a bare infrastructure span — each carries the operation,
    ``sut.name`` and scope IDs that tie it to the agent's memory.
    """
    keys = (ATTR_OPERATION, ATTR_SUT_NAME, ATTR_SCOPE_USER, ATTR_SCOPE_AGENT, ATTR_SCOPE_RUN)
    return {k: attrs[k] for k in keys if k in attrs}


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
                with tracer.start_as_current_span(f"memory.{op}", kind=SpanKind.CLIENT, attributes=attrs) as span:
                    ctx_token = _active_op_attrs.set(_agent_memory_ctx(attrs))
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
                        _active_op_attrs.reset(ctx_token)
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
            with tracer.start_as_current_span(f"memory.{op}", kind=SpanKind.CLIENT, attributes=attrs) as span:
                ctx_token = _active_op_attrs.set(_agent_memory_ctx(attrs))
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
                    _active_op_attrs.reset(ctx_token)
                    duration = time.perf_counter() - start
                    derived = _result_metrics(op, result) if status == "ok" else {}
                    for k, v in derived.items():
                        span.set_attribute(k, v)
                    _record_metrics(op, _store_kind(self), duration, status, derived)
                    _emit_log(op, {**attrs, **derived}, duration, status, error)
                return result

        return sync_wrapper

    return decorator


# --------------------------------------------------------------------------- #
# End-to-end trace: child spans for the internal pipeline.                     #
#                                                                             #
# A ``memory.<op>`` span on its own is a single flat span. To render a real    #
# *end-to-end* trace (embedding → vector store → LLM, the way a distributed    #
# waterfall shows a caller → backend), we wrap the embedder / vector store /   #
# LLM component methods so each internal call emits a **child span** under the  #
# currently-active memory span. Because ``start_as_current_span`` reads the     #
# active context (propagated into ``asyncio.to_thread`` worker threads via      #
# ``contextvars``), these children nest correctly for both ``Memory`` and       #
# ``AsyncMemory`` without touching a single call site.                         #
# --------------------------------------------------------------------------- #
def _inside_recording_span() -> bool:
    """True only when a recording span (i.e. a live ``memory.<op>``) is active.

    Gating on this keeps component child spans strictly *within* a memory
    operation — component calls made during ``__init__`` never create stray
    root spans.
    """
    try:
        span = _otel_trace.get_current_span()
        return bool(span) and span.get_span_context().is_valid and span.is_recording()
    except Exception:  # pragma: no cover - defensive
        return False


def _child_span_wrapper(span_name, kind, static_attrs, dyn_attrs, func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not _ENABLED or not _inside_recording_span():
            return func(*args, **kwargs)
        attrs = dict(static_attrs)
        # Stamp the agent-memory identity of the enclosing op onto this child span
        # so it is not a bare infra span (operation + sut.name + scope IDs).
        op_ctx = _active_op_attrs.get()
        if op_ctx:
            attrs.update(op_ctx)
        if dyn_attrs is not None:
            try:
                attrs.update({k: v for k, v in dyn_attrs(args, kwargs).items() if v is not None})
            except Exception:  # pragma: no cover - defensive
                pass
        with _get_tracer().start_as_current_span(span_name, kind=kind, attributes=attrs) as span:
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                span.set_status(Status(StatusCode.ERROR, f"{type(exc).__name__}: {exc}"))
                span.record_exception(exc)
                raise

    wrapper._mem0_traced = True  # idempotency guard against double-wrapping
    return wrapper


def trace_components(instance: Any) -> None:
    """Wrap ``embedding_model`` / ``vector_store`` / ``llm`` methods of a Memory
    instance so their calls emit child spans, producing an end-to-end trace.

    Safe to call once per instance from ``__init__``. No-op when instrumentation
    is disabled or the OTel API is absent, and idempotent per component method.
    """
    if not _ENABLED:
        return

    try:
        backend = _store_kind(instance)
    except Exception:  # pragma: no cover - defensive
        backend = "unknown"
    embed_provider = None
    llm_provider = None
    try:
        embed_provider = getattr(getattr(instance.config, "embedder", None), "provider", None)
        llm_provider = getattr(getattr(instance.config, "llm", None), "provider", None)
    except Exception:  # pragma: no cover - defensive
        pass

    def _embed_action(args, kwargs):
        # embed(text, memory_action) / embed_batch(texts, memory_action) — bound
        # method, so ``self`` is not in ``args``.
        action = args[1] if len(args) > 1 else kwargs.get("memory_action") or kwargs.get("action")
        return {ATTR_EMBEDDING_ACTION: action}

    # (component, methods, span-name builder, kind, static attrs, dyn-attr fn)
    specs = [
        (
            getattr(instance, "embedding_model", None),
            ("embed", "embed_batch"),
            lambda m: "memory.embed",
            SpanKind.INTERNAL,
            {ATTR_EMBEDDING_MODEL: embed_provider},
            _embed_action,
        ),
        (
            getattr(instance, "vector_store", None),
            ("search", "insert", "get", "list", "update", "delete", "keyword_search"),
            lambda m: f"memory.vector_store.{m}",
            SpanKind.CLIENT,
            {ATTR_STORE_BACKEND: backend},
            None,
        ),
        (
            getattr(instance, "llm", None),
            ("generate_response",),
            lambda m: "memory.llm.generate",
            SpanKind.CLIENT,
            {ATTR_LLM_MODEL: llm_provider},
            None,
        ),
    ]

    for comp, methods, name_of, kind, static_attrs, dyn in specs:
        if comp is None:
            continue
        for method_name in methods:
            fn = getattr(comp, method_name, None)
            if not callable(fn) or getattr(fn, "_mem0_traced", False):
                continue
            attrs = {k: v for k, v in static_attrs.items() if v is not None}
            if kind is SpanKind.CLIENT and comp is getattr(instance, "vector_store", None):
                attrs = {**attrs, ATTR_DB_OPERATION: method_name}
            try:
                setattr(comp, method_name, _child_span_wrapper(name_of(method_name), kind, attrs, dyn, fn))
            except Exception:  # pragma: no cover - some clients forbid setattr
                logger.debug("mem0 otel: could not wrap %s.%s for tracing", comp, method_name)

    return


# --------------------------------------------------------------------------- #
# Server boundary: continue the *agent's* trace into the memory server.        #
#                                                                             #
# The library spans above nest under whatever span is active in-process. For a #
# distributed ``agent → memory server → mem0`` trace, the server must *extract* #
# the inbound W3C ``traceparent`` and open a SERVER span with it as parent —    #
# then the ``memory.<op>`` spans (and their children) join the agent's trace   #
# instead of starting a fresh single-span root. ``start_server_span`` does this #
# with the OTel **API only** (``opentelemetry.propagate``), so it stays within  #
# the soft-dependency contract.                                                 #
# --------------------------------------------------------------------------- #
def start_server_span(name: str, headers: Optional[Dict[str, str]] = None, attributes: Optional[Dict[str, Any]] = None):
    """Return a context manager for a SERVER span whose parent is extracted from
    ``headers`` (W3C ``traceparent`` / ``tracestate``). No-op context manager
    when instrumentation is disabled or the API is absent.

    Usage in an ASGI/HTTP middleware::

        with otel.start_server_span(f"{req.method} {req.url.path}", dict(req.headers)):
            response = await call_next(req)
    """
    if not _ENABLED:
        return contextlib.nullcontext()
    try:
        from opentelemetry.propagate import extract

        parent_ctx = extract(headers or {})
        span_attrs = {ATTR_SUT_NAME: SUT_NAME}
        if attributes:
            span_attrs.update({k: v for k, v in attributes.items() if v is not None})
        return _get_tracer().start_as_current_span(
            name, context=parent_ctx, kind=SpanKind.SERVER, attributes=span_attrs
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("mem0 otel: start_server_span failed: %s", exc)
        return contextlib.nullcontext()


def bootstrap_tracing(service_name: str = SUT_NAME) -> bool:
    """Best-effort app-side SDK setup for services that want turnkey OTLP export.

    Libraries must never install an SDK, but an *application* (the mem0 server)
    may. This configures a ``TracerProvider`` + OTLP span exporter **only when**
    ``opentelemetry-sdk`` / the OTLP exporter are importable and
    ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set. Returns ``True`` if tracing was set
    up, ``False`` (no-op) otherwise. Respects an already-installed provider.
    """
    if not _ENABLED or not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        return False
    try:
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        current = _otel_trace.get_tracer_provider()
        # Don't clobber a provider an operator already installed (e.g. via
        # ``opentelemetry-instrument``).
        if isinstance(current, TracerProvider):
            return False
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        except Exception:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # type: ignore

        provider = TracerProvider(resource=Resource.create({"service.name": service_name, ATTR_SUT_NAME: SUT_NAME}))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        _otel_trace.set_tracer_provider(provider)
        reset_for_testing()  # re-resolve our cached tracer against the new provider
        return True
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("mem0 otel: bootstrap_tracing skipped: %s", exc)
        return False
