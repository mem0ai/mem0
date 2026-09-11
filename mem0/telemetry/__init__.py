"""mem0 telemetry helpers.

Currently exposes the OpenTelemetry instrumentation layer (spans, metrics,
logs) for the open-source ``Memory`` / ``AsyncMemory`` classes. Import is
side-effect free and safe even when ``opentelemetry-api`` is not installed.
"""

from mem0.telemetry.otel import instrument, is_enabled

__all__ = ["instrument", "is_enabled"]
