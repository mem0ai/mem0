"""Tracing distribuído com OpenTelemetry (task_08 / ADR-004).

Degradação graciosa: se os pacotes OpenTelemetry não estiverem instalados ou se
``OTEL_SDK_DISABLED`` estiver setado, ``configure_tracing`` é um no-op que
retorna ``False`` — a aplicação continua funcionando sem tracing.

Auto-instrumenta FastAPI, HTTPX (cobre embed/LLM/Qdrant via HTTP) e SQLAlchemy.
A correlação com ``request_id``/``job_id`` é feita em ``logging_context`` via
``current_trace_id``.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def _disabled() -> bool:
    return (os.getenv("OTEL_SDK_DISABLED", "").strip().lower()) in ("1", "true", "yes", "on")


def build_provider(service_name: str, *, span_exporter=None, use_batch: bool = True):
    """Cria um TracerProvider (sem alterar o global). Retorna ``None`` se OTel ausente."""
    try:
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            SimpleSpanProcessor,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenTelemetry SDK indisponível; tracing desativado: %s", exc)
        return None

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    exporter = span_exporter
    if exporter is None:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
            exporter = OTLPSpanExporter(endpoint=endpoint) if endpoint else OTLPSpanExporter()
        except Exception as exc:  # noqa: BLE001
            logger.warning("OTLP exporter indisponível: %s", exc)
            return provider  # provider sem processor: spans no-op, mas API válida

    processor = BatchSpanProcessor(exporter) if (use_batch and span_exporter is None) else SimpleSpanProcessor(exporter)
    provider.add_span_processor(processor)
    return provider


def configure_tracing(*, service_name: str = "openmemory-api", app=None, engine=None) -> bool:
    """Configura o tracing global e instrumenta FastAPI/HTTPX/SQLAlchemy.

    Idempotente e seguro: retorna ``False`` quando desativado/ausente.
    """
    if _disabled():
        logger.info("tracing desativado por OTEL_SDK_DISABLED")
        return False

    provider = build_provider(service_name)
    if provider is None:
        return False

    from opentelemetry import trace

    if getattr(trace.get_tracer_provider(), "_mem0_configured", False):
        return True
    provider._mem0_configured = True  # type: ignore[attr-defined]
    trace.set_tracer_provider(provider)
    _instrument(app, engine)
    return True


def _instrument(app, engine) -> None:
    if app is not None:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app)
        except Exception as exc:  # noqa: BLE001
            logger.warning("instrumentação FastAPI falhou: %s", exc)
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except Exception as exc:  # noqa: BLE001
        logger.warning("instrumentação HTTPX falhou: %s", exc)
    if engine is not None:
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

            SQLAlchemyInstrumentor().instrument(engine=engine)
        except Exception as exc:  # noqa: BLE001
            logger.warning("instrumentação SQLAlchemy falhou: %s", exc)


def get_tracer(name: str = "openmemory"):
    """Tracer do provider global (no-op se OTel ausente)."""
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except Exception:  # noqa: BLE001
        return None


def current_trace_id() -> str:
    """``trace_id`` (32 hex) do span corrente, ou ``""`` fora de um span/sem OTel."""
    try:
        from opentelemetry import trace

        ctx = trace.get_current_span().get_span_context()
        if ctx is not None and ctx.trace_id:
            return format(ctx.trace_id, "032x")
    except Exception:  # noqa: BLE001
        pass
    return ""


def _noop() -> Optional[str]:  # pragma: no cover - placeholder de extensão
    return None
