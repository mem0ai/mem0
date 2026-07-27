"""Unit tests for the mem0 OpenTelemetry instrumentation layer.

These tests exercise the ``@instrument`` decorator and its semconv output
against in-memory OTel exporters — no real vector store / LLM is required. A
lightweight ``FakeMemory`` stands in for ``Memory``/``AsyncMemory`` with the
same attribute surface the instrumentation reads.
"""

# ruff: noqa: E402  (imports intentionally follow the importorskip SDK guard)

import asyncio

import pytest

# Skip the whole module cleanly if the OTel SDK is not installed.
otel_sdk = pytest.importorskip("opentelemetry.sdk")

from opentelemetry import _logs as otel_logs
from opentelemetry import metrics as otel_metrics
from opentelemetry import trace as otel_trace
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import InMemoryLogExporter, SimpleLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from mem0.telemetry import otel


# --------------------------------------------------------------------------- #
# Fixtures: install in-memory OTel providers once, reset the module's cached   #
# tracer/meter/logger before each test.                                        #
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module", autouse=True)
def _install_providers():
    span_exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    otel_trace.set_tracer_provider(tracer_provider)

    metric_reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[metric_reader])
    otel_metrics.set_meter_provider(meter_provider)

    log_exporter = InMemoryLogExporter()
    logger_provider = LoggerProvider()
    logger_provider.add_log_record_processor(SimpleLogRecordProcessor(log_exporter))
    otel_logs.set_logger_provider(logger_provider)

    yield {
        "spans": span_exporter,
        "metrics": metric_reader,
        "logs": log_exporter,
    }


@pytest.fixture(autouse=True)
def _reset(_install_providers, monkeypatch):
    # Force instrumentation on and re-resolve providers against the in-memory ones.
    monkeypatch.setattr(otel, "_ENABLED", True)
    monkeypatch.setattr(otel, "_CAPTURE_QUERY_TEXT", True)
    monkeypatch.setattr(otel, "_QUERY_MAX_LEN", 256)
    otel.reset_for_testing()
    _install_providers["spans"].clear()
    _install_providers["logs"].clear()
    yield


# --------------------------------------------------------------------------- #
# A stand-in for Memory/AsyncMemory with the attributes the instrumentation    #
# reads (config.vector_store.provider, config.embedder.provider, dims).        #
# --------------------------------------------------------------------------- #
class _Cfg:
    class vector_store:
        provider = "qdrant"

    class embedder:
        provider = "openai"

    graph_store = None


class _EmbedCfg:
    embedding_dims = 1536


class _Embed:
    config = _EmbedCfg()


class FakeMemory:
    def __init__(self):
        self.config = _Cfg()
        self.embedding_model = _Embed()

    @otel.instrument("add")
    def add(self, messages, *, user_id=None, agent_id=None, run_id=None, infer=True):
        return [
            {"id": "m1", "memory": "likes tennis", "event": "ADD"},
            {"id": "m2", "memory": "lives in Paris", "event": "ADD"},
        ]

    @otel.instrument("search")
    def search(self, query, *, top_k=20, filters=None, threshold=0.1):
        return {"results": [{"id": "m1", "memory": "x", "score": 0.42}, {"id": "m2", "memory": "y", "score": 0.91}]}

    @otel.instrument("get")
    def get(self, memory_id):
        return {"id": memory_id, "memory": "x"} if memory_id == "hit" else None

    @otel.instrument("get_all")
    def get_all(self, *, filters=None, top_k=20):
        return {"results": [{"id": "m1"}, {"id": "m2"}, {"id": "m3"}]}

    @otel.instrument("update")
    def update(self, memory_id, text=None):
        return {"message": "Memory updated successfully!"}

    @otel.instrument("delete")
    def delete(self, memory_id):
        return {"message": "Memory deleted successfully!"}

    @otel.instrument("search")
    def search_boom(self, query, *, filters=None):
        raise ValueError("boom")


class FakeAsyncMemory(FakeMemory):
    @otel.instrument("add")
    async def add(self, messages, *, user_id=None, agent_id=None, run_id=None, infer=True):
        return [{"id": "m1", "memory": "async fact", "event": "ADD"}]

    @otel.instrument("search")
    async def search(self, query, *, top_k=20, filters=None, threshold=0.1):
        return {"results": [{"id": "m1", "memory": "x", "score": 0.77}]}


def _spans(providers):
    return providers["spans"].get_finished_spans()


def _metric_points(providers, name):
    data = providers["metrics"].get_metrics_data()
    points = []
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for metric in sm.metrics:
                if metric.name == name:
                    points.extend(metric.data.data_points)
    return points


def _find_point(providers, name, **labels):
    for p in _metric_points(providers, name):
        if all(p.attributes.get(k) == v for k, v in labels.items()):
            return p
    return None


def _counter_value(providers, name, **labels):
    # The module-scoped InMemoryMetricReader aggregates cumulatively, so tests
    # assert on the *delta* produced by a single call rather than absolutes.
    p = _find_point(providers, name, **labels)
    return p.value if p is not None else 0


def _hist_count_sum(providers, name, **labels):
    p = _find_point(providers, name, **labels)
    if p is None:
        return 0, 0.0
    return p.count, p.sum


# --------------------------------------------------------------------------- #
# Span tests                                                                   #
# --------------------------------------------------------------------------- #
def test_add_emits_span_with_semconv_attributes(_install_providers):
    FakeMemory().add("hello", user_id="u1", agent_id="a1")
    spans = _spans(_install_providers)
    assert len(spans) == 1
    span = spans[0]
    assert span.name == "memory.add"
    attrs = dict(span.attributes)
    assert attrs[otel.ATTR_OPERATION] == "add"
    assert attrs[otel.ATTR_SUT_NAME] == "mem0"
    assert attrs[otel.ATTR_STORE_BACKEND] == "qdrant"
    assert attrs[otel.ATTR_EMBEDDING_MODEL] == "openai"
    assert attrs[otel.ATTR_ARCHITECTURE] == "vector"
    assert attrs[otel.ATTR_VECTOR_DIMS] == 1536
    assert attrs[otel.ATTR_SCOPE_USER] == "u1"
    assert attrs[otel.ATTR_SCOPE_AGENT] == "a1"
    assert attrs[otel.ATTR_ITEM_COUNT] == 2
    assert attrs[otel.ATTR_BYTES] > 0


def test_search_captures_result_count_and_top_similarity(_install_providers):
    FakeMemory().search("what sports?", filters={"user_id": "u1"})
    span = _spans(_install_providers)[0]
    attrs = dict(span.attributes)
    assert span.name == "memory.search"
    assert attrs[otel.ATTR_RESULT_COUNT] == 2
    assert attrs[otel.ATTR_TOP_SIMILARITY] == pytest.approx(0.91)
    assert attrs[otel.ATTR_SCOPE_USER] == "u1"  # pulled from filters dict


def test_get_hit_and_miss(_install_providers):
    FakeMemory().get("hit")
    FakeMemory().get("nope")
    spans = _spans(_install_providers)
    hit = dict(spans[0].attributes)
    miss = dict(spans[1].attributes)
    assert hit[otel.ATTR_HIT] is True
    assert miss[otel.ATTR_HIT] is False


def test_get_all_result_count(_install_providers):
    FakeMemory().get_all(filters={"agent_id": "a9"})
    attrs = dict(_spans(_install_providers)[0].attributes)
    assert attrs[otel.ATTR_RESULT_COUNT] == 3
    assert attrs[otel.ATTR_SCOPE_AGENT] == "a9"


# --------------------------------------------------------------------------- #
# PII / cardinality tests                                                      #
# --------------------------------------------------------------------------- #
def test_query_text_truncated(_install_providers, monkeypatch):
    monkeypatch.setattr(otel, "_QUERY_MAX_LEN", 8)
    FakeMemory().search("abcdefghijklmnop", filters={"user_id": "u1"})
    attrs = dict(_spans(_install_providers)[0].attributes)
    assert attrs[otel.ATTR_QUERY_LENGTH] == 16
    assert attrs[otel.ATTR_QUERY_TEXT] == "abcdefgh…"


def test_query_text_redacted_when_disabled(_install_providers, monkeypatch):
    monkeypatch.setattr(otel, "_CAPTURE_QUERY_TEXT", False)
    FakeMemory().search("secret query", filters={"user_id": "u1"})
    attrs = dict(_spans(_install_providers)[0].attributes)
    assert otel.ATTR_QUERY_TEXT not in attrs  # redacted
    assert attrs[otel.ATTR_QUERY_LENGTH] == 12  # length still recorded


def test_query_never_a_metric_label(_install_providers):
    FakeMemory().search("some private text", filters={"user_id": "u1"})
    points = _metric_points(_install_providers, otel.METRIC_OP_DURATION)
    assert points
    for p in points:
        assert "memory.query.text" not in p.attributes
        assert "user_id" not in p.attributes
        # only the bounded label set is present
        assert set(p.attributes.keys()) <= {"operation", "store_kind", "sut_name", "status"}


# --------------------------------------------------------------------------- #
# Metric tests                                                                 #
# --------------------------------------------------------------------------- #
def test_duration_histogram_recorded(_install_providers):
    labels = {"operation": "add", "store_kind": "qdrant", "sut_name": "mem0", "status": "ok"}
    count_before, _ = _hist_count_sum(_install_providers, otel.METRIC_OP_DURATION, **labels)
    FakeMemory().add("hi", user_id="u1")
    count_after, _ = _hist_count_sum(_install_providers, otel.METRIC_OP_DURATION, **labels)
    assert count_after - count_before == 1


def test_recall_results_and_top_similarity_metrics(_install_providers):
    rc_labels = {"operation": "search", "store_kind": "qdrant", "sut_name": "mem0"}
    rc_before_count, rc_before_sum = _hist_count_sum(_install_providers, otel.METRIC_RECALL_RESULTS, **rc_labels)
    FakeMemory().search("q", filters={"user_id": "u1"})
    rc_after_count, rc_after_sum = _hist_count_sum(_install_providers, otel.METRIC_RECALL_RESULTS, **rc_labels)
    assert rc_after_count - rc_before_count == 1
    assert rc_after_sum - rc_before_sum == 2  # two results this call
    ts = _find_point(_install_providers, otel.METRIC_RECALL_TOP_SIM, **rc_labels)
    assert ts is not None and ts.max == pytest.approx(0.91)


def test_items_and_bytes_counters(_install_providers):
    labels = {"operation": "add", "store_kind": "qdrant", "sut_name": "mem0"}
    items_before = _counter_value(_install_providers, otel.METRIC_ITEMS_TOTAL, **labels)
    bytes_before = _counter_value(_install_providers, otel.METRIC_BYTES_TOTAL, **labels)
    FakeMemory().add("hi", user_id="u1")
    items_after = _counter_value(_install_providers, otel.METRIC_ITEMS_TOTAL, **labels)
    bytes_after = _counter_value(_install_providers, otel.METRIC_BYTES_TOTAL, **labels)
    assert items_after - items_before == 2
    assert bytes_after - bytes_before > 0


# --------------------------------------------------------------------------- #
# Log tests                                                                    #
# --------------------------------------------------------------------------- #
def test_log_record_emitted_and_trace_correlated(_install_providers):
    FakeMemory().add("hi", user_id="u1")
    logs = _install_providers["logs"].get_finished_logs()
    assert len(logs) == 1
    record = logs[0].log_record
    assert record.body == "memory.add ok"
    assert record.attributes[otel.ATTR_OPERATION] == "add"
    # Correlated with the span's trace.
    span = _spans(_install_providers)[0]
    assert record.trace_id == span.context.trace_id


# --------------------------------------------------------------------------- #
# Error-path tests                                                             #
# --------------------------------------------------------------------------- #
def test_error_sets_span_status_and_metric_status(_install_providers):
    with pytest.raises(ValueError):
        FakeMemory().search_boom("q", filters={"user_id": "u1"})
    span = _spans(_install_providers)[0]
    from opentelemetry.trace import StatusCode

    assert span.status.status_code == StatusCode.ERROR
    assert any(e.name == "exception" for e in span.events)
    points = _metric_points(_install_providers, otel.METRIC_OP_DURATION)
    err = [p for p in points if p.attributes.get("status") == "error"]
    assert err
    logs = _install_providers["logs"].get_finished_logs()
    assert logs[-1].log_record.body == "memory.search error"


# --------------------------------------------------------------------------- #
# Async mirror                                                                 #
# --------------------------------------------------------------------------- #
def test_async_add_and_search(_install_providers):
    async def run():
        mem = FakeAsyncMemory()
        await mem.add("hi", user_id="u1")
        await mem.search("q", filters={"user_id": "u1"})

    asyncio.run(run())
    spans = _spans(_install_providers)
    names = sorted(s.name for s in spans)
    assert names == ["memory.add", "memory.search"]
    search_attrs = dict(next(s for s in spans if s.name == "memory.search").attributes)
    assert search_attrs[otel.ATTR_TOP_SIMILARITY] == pytest.approx(0.77)


# --------------------------------------------------------------------------- #
# Graceful degradation                                                         #
# --------------------------------------------------------------------------- #
def test_disabled_is_passthrough_noop(_install_providers, monkeypatch):
    monkeypatch.setattr(otel, "_ENABLED", False)
    result = FakeMemory().add("hi", user_id="u1")
    assert result[0]["id"] == "m1"
    assert list(_spans(_install_providers)) == []  # no spans when disabled
