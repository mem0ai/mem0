"""Smoke test: emit mem0 memory-semconv telemetry through the real OTel SDK.

Unlike ``test_otel.py`` (which asserts against in-memory exporters), this script
wires the **OTLP-stdout / Console** exporters — the SDK path a production
deployment uses — and drives the *shipping* ``@otel_instrument`` decorator (the
exact one applied to ``mem0.memory.main.Memory`` / ``AsyncMemory``) across all
six operations plus an error case. It then force-flushes and verifies the
memory-semconv v0.1.0 span attributes, metric names, and log records appear in
the exported output.

Run:
    python tests/telemetry/smoke_otel.py

Exit code 0 = every required signal + semconv name was exported.
"""

import io
import sys

from opentelemetry import _logs as otel_logs
from opentelemetry import metrics as otel_metrics
from opentelemetry import trace as otel_trace
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import ConsoleLogExporter, SimpleLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

from mem0.telemetry import otel

# --------------------------------------------------------------------------- #
# 1. Configure the real SDK with stdout (Console = OTLP-JSON-to-stdout).       #
#    Resource carries the memory-semconv service identity.                     #
# --------------------------------------------------------------------------- #
resource = Resource.create(
    {
        "service.name": "mem0",
        otel.ATTR_SUT_NAME: otel.SUT_NAME,
        otel.ATTR_ARCHITECTURE: "vector",
    }
)

# Send every signal to a single in-memory buffer so the run is inspectable and
# assertable. (Console exporters emit OTLP-shaped JSON — the stdout path.)
buf = io.StringIO()

tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter(out=buf)))
otel_trace.set_tracer_provider(tracer_provider)

metric_reader = PeriodicExportingMetricReader(
    ConsoleMetricExporter(out=buf), export_interval_millis=3_600_000
)
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
otel_metrics.set_meter_provider(meter_provider)

logger_provider = LoggerProvider(resource=resource)
logger_provider.add_log_record_processor(SimpleLogRecordProcessor(ConsoleLogExporter(out=buf)))
otel_logs.set_logger_provider(logger_provider)

otel.reset_for_testing()  # re-resolve against the providers just installed


# --------------------------------------------------------------------------- #
# 2. A Memory-shaped object decorated with the SHIPPING instrumentation.       #
# --------------------------------------------------------------------------- #
class _Cfg:
    class vector_store:
        provider = "qdrant"

    class embedder:
        provider = "openai"

    graph_store = None


class _Embed:
    class config:
        embedding_dims = 1536


class DemoMemory:
    def __init__(self):
        self.config = _Cfg()
        self.embedding_model = _Embed()

    @otel.instrument("add")
    def add(self, messages, *, user_id=None, agent_id=None, run_id=None, infer=True):
        return [{"id": "mem_1", "memory": "Alex plays tennis on weekends", "event": "ADD"}]

    @otel.instrument("search")
    def search(self, query, *, top_k=20, filters=None, threshold=0.1):
        return {"results": [{"id": "mem_1", "memory": "plays tennis", "score": 0.88}]}

    @otel.instrument("get")
    def get(self, memory_id):
        return {"id": memory_id, "memory": "plays tennis"}

    @otel.instrument("get_all")
    def get_all(self, *, filters=None, top_k=20):
        return {"results": [{"id": "mem_1"}, {"id": "mem_2"}]}

    @otel.instrument("update")
    def update(self, memory_id, text=None):
        return {"message": "Memory updated successfully!"}

    @otel.instrument("delete")
    def delete(self, memory_id):
        return {"message": "Memory deleted successfully!"}

    @otel.instrument("search")
    def search_error(self, query, *, filters=None):
        raise RuntimeError("vector store unreachable")


# --------------------------------------------------------------------------- #
# 3. Drive all six operations + an error, capturing stdout.                    #
# --------------------------------------------------------------------------- #
mem = DemoMemory()
mem.add(
    [{"role": "user", "content": "I play tennis on weekends"}],
    user_id="alex",
    agent_id="coach",
)
mem.search("what sports does alex play?", filters={"user_id": "alex"})
mem.get("mem_1")
mem.get_all(filters={"user_id": "alex"})
mem.update("mem_1", text="Alex plays tennis and padel")
mem.delete("mem_1")
try:
    mem.search_error("boom", filters={"user_id": "alex"})
except RuntimeError:
    pass

# Flush all three signal pipelines into the buffer.
tracer_provider.force_flush()
meter_provider.force_flush()
logger_provider.force_flush()

out = buf.getvalue()
# Echo the real exported telemetry so the smoke run is inspectable.
print(out)


# --------------------------------------------------------------------------- #
# 4. Validate the memory-semconv v0.1.0 surface is present in the export.      #
# --------------------------------------------------------------------------- #
required_span_names = [
    "memory.add",
    "memory.search",
    "memory.get",
    "memory.get_all",
    "memory.update",
    "memory.delete",
]
required_span_attrs = [
    otel.ATTR_OPERATION,
    otel.ATTR_SUT_NAME,
    otel.ATTR_STORE_BACKEND,
    otel.ATTR_ARCHITECTURE,
    otel.ATTR_EMBEDDING_MODEL,
    otel.ATTR_VECTOR_DIMS,
    otel.ATTR_QUERY_LENGTH,
    otel.ATTR_QUERY_TEXT,
    otel.ATTR_RESULT_COUNT,
    otel.ATTR_TOP_SIMILARITY,
    otel.ATTR_ITEM_COUNT,
    otel.ATTR_SCOPE_USER,
]
required_metric_names = [
    otel.METRIC_OP_DURATION,
    otel.METRIC_RECALL_RESULTS,
    otel.METRIC_RECALL_TOP_SIM,
    otel.METRIC_ITEMS_TOTAL,
    otel.METRIC_BYTES_TOTAL,
]

failures = []
for name in required_span_names:
    if f'"name": "{name}"' not in out and f"'name': '{name}'" not in out:
        failures.append(f"missing span: {name}")
for attr in required_span_attrs:
    if attr not in out:
        failures.append(f"missing span attribute: {attr}")
for name in required_metric_names:
    if name not in out:
        failures.append(f"missing metric: {name}")
# Error signal: ERROR status/severity must have been exported.
if "ERROR" not in out and "STATUS_CODE_ERROR" not in out:
    failures.append("missing error status on failed operation")
# Log correlation: a log body should reference a memory op.
if "memory.add ok" not in out and "memory.search ok" not in out:
    failures.append("missing structured log record")

# PII guard: the raw query must NOT appear on any metric data point. We assert
# it only shows up in span attributes, never in the metric export block.
if '"memory.query.text"' in out or "memory.query.text" in out:
    # It's allowed (span-only). Confirm no metric label carries it:
    # ConsoleMetricExporter emits data points with an "attributes" dict — the
    # query string must never appear there. Heuristic: the query substring must
    # not co-occur inside a metrics 'data_points' fragment.
    for metric_name in required_metric_names:
        idx = out.find(metric_name)
        if idx != -1:
            window = out[idx : idx + 1500]
            if "what sports does alex play" in window:
                failures.append(f"PII LEAK: query text in metric labels of {metric_name}")

print("=" * 70)
if failures:
    print("SMOKE TEST FAILED:")
    for f in failures:
        print("  -", f)
    sys.exit(1)

print("SMOKE TEST PASSED")
print(f"  spans validated:   {len(required_span_names)}")
print(f"  span attrs found:  {len(required_span_attrs)}")
print(f"  metrics validated: {len(required_metric_names)}")
print("  error status + structured logs exported: yes")
print("  PII guard (query text absent from metric labels): yes")
sys.exit(0)
