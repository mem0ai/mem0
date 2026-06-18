"""Tests for OpenTelemetry tracing wiring (task_08 / ADR-004)."""

import logging
import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.utils.tracing import build_provider, configure_tracing, current_trace_id


def test_configure_tracing_disabled_returns_false(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    assert configure_tracing(service_name="t") is False


def test_span_is_exported_and_trace_id_available():
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    provider = build_provider("test-svc", span_exporter=exporter, use_batch=False)
    assert provider is not None
    tracer = provider.get_tracer("t")

    assert current_trace_id() == ""  # fora de qualquer span
    with tracer.start_as_current_span("op"):
        tid = current_trace_id()
        assert len(tid) == 32 and int(tid, 16) != 0

    provider.force_flush()
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "op"


def test_logging_filter_injects_trace_id():
    from app.utils.logging_context import StructuredContextFilter

    record = logging.LogRecord("n", logging.INFO, __file__, 1, "msg", None, None)
    StructuredContextFilter().filter(record)
    assert hasattr(record, "trace_id")
    # Fora de um span o pivô fica "-".
    assert record.trace_id == "-"
