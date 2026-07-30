"""Live-collector deploy test: ship mem0 memory-semconv telemetry over real OTLP.

Unlike ``smoke_otel.py`` (Console/stdout SDK exporters), this drives the shipping
``@otel_instrument`` decorator across all six operations and exports every signal
over **OTLP/gRPC** to a running OpenTelemetry Collector. It is the exact SDK +
wire path a production deployment uses.

Configure the target with the standard OTel env vars, e.g.::

    OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4317 \
    OTEL_EXPORTER_OTLP_INSECURE=true \
    python tests/telemetry/otlp_export_demo.py

For an authenticated gateway (e.g. a Dynatrace-backed OTel collector), also set
``OTEL_EXPORTER_OTLP_HEADERS`` (e.g. ``Authorization=Api-Token dt0c01...``) and
drop ``OTEL_EXPORTER_OTLP_INSECURE`` for TLS.

Exit code 0 = all three signals force-flushed to the collector without error.
"""

import os
import sys

from opentelemetry import _logs as otel_logs
from opentelemetry import metrics as otel_metrics
from opentelemetry import trace as otel_trace
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from mem0.telemetry import otel

ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4317")
INSECURE = os.environ.get("OTEL_EXPORTER_OTLP_INSECURE", "true").lower() in ("1", "true", "yes")

resource = Resource.create(
    {
        "service.name": os.environ.get("OTEL_SERVICE_NAME", "mem0"),
        otel.ATTR_SUT_NAME: otel.SUT_NAME,
        otel.ATTR_ARCHITECTURE: "vector",
    }
)

tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=ENDPOINT, insecure=INSECURE)))
otel_trace.set_tracer_provider(tracer_provider)

metric_reader = PeriodicExportingMetricReader(
    OTLPMetricExporter(endpoint=ENDPOINT, insecure=INSECURE), export_interval_millis=3_600_000
)
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
otel_metrics.set_meter_provider(meter_provider)

logger_provider = LoggerProvider(resource=resource)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(endpoint=ENDPOINT, insecure=INSECURE)))
otel_logs.set_logger_provider(logger_provider)

otel.reset_for_testing()  # re-resolve the instrument singletons against these providers


class _Cfg:
    class vector_store:
        provider = "qdrant"

    class embedder:
        provider = "openai"

    class llm:
        provider = "openai"

    graph_store = None


class _Embed:
    class config:
        embedding_dims = 1536

    def embed(self, text, memory_action=None):
        return [0.01, 0.02, 0.03]

    def embed_batch(self, texts, memory_action=None):
        return [[0.01, 0.02, 0.03] for _ in texts]


class _VectorStore:
    def search(self, *a, **k):
        return [{"id": "mem_1", "score": 0.88}]

    def insert(self, *a, **k):
        return None

    def get(self, *a, **k):
        return {"id": "mem_1"}

    def list(self, *a, **k):
        return {"results": [{"id": "mem_1"}, {"id": "mem_2"}]}

    def update(self, *a, **k):
        return None

    def delete(self, *a, **k):
        return None


class _LLM:
    def generate_response(self, *a, **k):
        return '{"facts": ["Alex plays tennis on weekends"]}'


class DemoMemory:
    """Memory-shaped object whose ops actually drive the embedder / vector store
    / LLM, so ``trace_components`` produces a real end-to-end trace tree."""

    def __init__(self):
        self.config = _Cfg()
        self.embedding_model = _Embed()
        self.vector_store = _VectorStore()
        self.llm = _LLM()
        otel.trace_components(self)  # wrap components -> child spans

    @otel.instrument("add")
    def add(self, messages, *, user_id=None, agent_id=None, run_id=None, infer=True):
        # Mirrors the real add() pipeline: embed -> recall -> LLM extract -> upsert.
        self.embedding_model.embed(str(messages), "add")
        self.vector_store.search("recall existing")
        self.llm.generate_response(messages=messages)
        self.vector_store.insert(vectors=[[0.01]], ids=["mem_1"], payloads=[{}])
        return [{"id": "mem_1", "memory": "Alex plays tennis on weekends", "event": "ADD"}]

    @otel.instrument("search")
    def search(self, query, *, top_k=20, filters=None, threshold=0.1):
        self.embedding_model.embed(query, "search")
        hits = self.vector_store.search(query)
        return {"results": [{"id": "mem_1", "memory": "plays tennis", "score": hits[0]["score"]}]}

    @otel.instrument("get")
    def get(self, memory_id):
        self.vector_store.get(vector_id=memory_id)
        return {"id": memory_id, "memory": "plays tennis"}

    @otel.instrument("get_all")
    def get_all(self, *, filters=None, top_k=20):
        return self.vector_store.list(filters=filters, top_k=top_k)

    @otel.instrument("update")
    def update(self, memory_id, text=None):
        self.embedding_model.embed(text or "", "update")
        self.vector_store.update(vector_id=memory_id)
        return {"message": "Memory updated successfully!"}

    @otel.instrument("delete")
    def delete(self, memory_id):
        self.vector_store.delete(vector_id=memory_id)
        return {"message": "Memory deleted successfully!"}

    @otel.instrument("search")
    def search_error(self, query, *, filters=None):
        self.embedding_model.embed(query, "search")
        raise RuntimeError("vector store unreachable")


def main():
    print(f"Exporting mem0 telemetry over OTLP/gRPC -> {ENDPOINT} (insecure={INSECURE})")
    mem = DemoMemory()
    # Wrap the whole flow in a caller span so the export shows a full end-to-end
    # waterfall: caller -> memory.<op> -> embed / vector_store / llm children —
    # the exact shape a distributed trace (e.g. an MCP memory server calling
    # mem0, which calls its backend) renders.
    caller = otel_trace.get_tracer("mem0.demo.caller")
    with caller.start_as_current_span("mcp-memory-server.request", kind=otel_trace.SpanKind.SERVER):
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

    ok = True
    ok &= tracer_provider.force_flush(timeout_millis=10_000)
    ok &= meter_provider.force_flush(timeout_millis=10_000)
    ok &= logger_provider.force_flush(timeout_millis=10_000)
    tracer_provider.shutdown()
    meter_provider.shutdown()
    logger_provider.shutdown()

    if ok:
        print("OTLP EXPORT OK: 6 ops + 1 error flushed (traces + metrics + logs) to the collector")
        sys.exit(0)
    print("OTLP EXPORT FAILED: force_flush reported an error (collector unreachable?)")
    sys.exit(1)


if __name__ == "__main__":
    main()
