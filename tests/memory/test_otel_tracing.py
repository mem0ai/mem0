"""Tests for the optional OpenTelemetry tracing layer (``mem0.memory.otel``).

These exercise the spans emitted by the public ``add`` / ``search`` methods on
both ``Memory`` and ``AsyncMemory``: the ``gen_ai.memory.client`` operation
span, the internal phase child spans nested underneath it, content gating, the
error path, and the no-op behavior when tracing is unavailable.
"""

import pytest

pytest.importorskip("opentelemetry.sdk")

from unittest.mock import MagicMock, Mock  # noqa: E402

from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter  # noqa: E402
from opentelemetry.trace import SpanKind  # noqa: E402

from mem0.exceptions import LLMError  # noqa: E402
from mem0.memory import otel  # noqa: E402
from mem0.memory.main import AsyncMemory, Memory  # noqa: E402

_EXPORTER = InMemorySpanExporter()
_PROVIDER = TracerProvider()
_PROVIDER.add_span_processor(SimpleSpanProcessor(_EXPORTER))

_EXTRACTION = '{"memory": [{"text": "Alice met Bob"}, {"text": "Bob called Alice"}]}'


def _setup_mocks(mocker):
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

    mock_vector_store = mocker.MagicMock()
    mock_vector_store.return_value.search.return_value = []
    mocker.patch(
        "mem0.utils.factory.VectorStoreFactory.create",
        side_effect=[mock_vector_store.return_value, mocker.MagicMock()],
    )

    mock_llm = mocker.MagicMock()
    mocker.patch("mem0.utils.factory.LlmFactory.create", mock_llm)
    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())
    return mock_llm, mock_vector_store


def _spans():
    return {s.name: s for s in _EXPORTER.get_finished_spans()}


@pytest.fixture(autouse=True)
def _otel_env(mocker, monkeypatch):
    # Route mem0's tracer at an in-memory provider, independent of any global one.
    monkeypatch.setattr(otel, "_get_tracer", lambda: _PROVIDER.get_tracer("mem0-test"))
    # Silence unrelated side effects (telemetry, notices) and heavy NLP so the
    # tests exercise only the instrumentation.
    mocker.patch("mem0.memory.main.capture_event")
    mocker.patch("mem0.memory.main.extract_entities", return_value=[])
    mocker.patch("mem0.memory.main.extract_entities_batch", return_value=[])
    mocker.patch("mem0.memory.main.lemmatize_for_bm25", side_effect=lambda q: q)
    mocker.patch("mem0.memory.main.detect_temporal_usage_from_metadata", return_value=None)
    mocker.patch("mem0.memory.main.detect_temporal_usage_from_search", return_value=None)
    mocker.patch("mem0.memory.main.detect_scale_threshold_from_add_result", return_value=None)
    mocker.patch("mem0.memory.main.detect_scale_threshold_from_top_k", return_value=None)
    for name in (
        "display_first_run_notice",
        "display_first_run_notice_async",
        "display_scale_threshold_notice",
        "display_scale_threshold_notice_async",
        "display_temporal_usage_notice",
        "display_temporal_usage_notice_async",
        "display_performance_slow_query_notice",
        "display_performance_slow_query_notice_async",
    ):
        mocker.patch(f"mem0.memory.main.{name}")
    _EXPORTER.clear()
    yield
    _EXPORTER.clear()


def _wire(memory):
    memory.custom_instructions = None
    memory.api_version = "v1.1"
    memory.llm.generate_response.return_value = _EXTRACTION
    memory.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])
    memory.embedding_model.embed_batch = Mock(side_effect=lambda texts, action="add": [[0.1, 0.2, 0.3] for _ in texts])
    memory.vector_store.search = Mock(return_value=[])
    memory.vector_store.keyword_search = Mock(return_value=None)
    memory.vector_store.insert = Mock()
    memory.db.get_last_messages = MagicMock(return_value=[])
    memory.db.save_messages = MagicMock()
    memory.db.batch_add_history = MagicMock()
    memory.db.add_history = MagicMock()
    return memory


def _memory(mocker):
    _setup_mocks(mocker)
    return _wire(Memory())


def _async_memory(mocker):
    _setup_mocks(mocker)
    return _wire(AsyncMemory())


class TestAddTracing:
    def test_add_emits_operation_span(self, mocker):
        result = _memory(mocker).add("Alice met Bob; Bob called Alice", user_id="u1")
        parent = _spans()[otel.OP_ADD]
        assert parent.kind == SpanKind.CLIENT
        assert parent.attributes[otel.GEN_AI_OPERATION_NAME] == "upsert_memory"
        assert parent.attributes[otel.GEN_AI_MEMORY_RECORD_COUNT] == len(result["results"])

    def test_add_emits_phase_children_nested_under_parent(self, mocker):
        _memory(mocker).add("Alice met Bob", user_id="u1")
        spans = _spans()
        parent = spans[otel.OP_ADD]
        for child_name in (
            "mem0.add.retrieve_existing",
            "mem0.add.llm_extract",
            "mem0.add.embed_memories",
            "mem0.add.vector_write",
        ):
            assert child_name in spans, child_name
            child = spans[child_name]
            assert child.kind == SpanKind.INTERNAL
            assert child.parent is not None
            assert child.parent.span_id == parent.context.span_id
            assert child.context.trace_id == parent.context.trace_id

    def test_add_error_records_error_type_and_reraises(self, mocker):
        memory = _memory(mocker)
        memory.llm.generate_response.side_effect = RuntimeError("boom")
        with pytest.raises(LLMError):
            memory.add("x", user_id="u1")
        parent = _spans()[otel.OP_ADD]
        assert parent.attributes[otel.ERROR_TYPE] == "LLMError"
        assert parent.status.status_code.name == "ERROR"

    def test_procedural_add_annotates_record_count(self, mocker):
        memory = _memory(mocker)
        mocker.patch.object(memory, "_create_memory", return_value="mem-1")
        result = memory.add("summarize this workflow", agent_id="a1", memory_type="procedural_memory")
        parent = _spans()[otel.OP_ADD]
        assert parent.attributes[otel.GEN_AI_OPERATION_NAME] == "upsert_memory"
        assert parent.attributes[otel.GEN_AI_MEMORY_RECORD_COUNT] == len(result["results"])


class TestSearchTracing:
    def test_search_emits_operation_span(self, mocker):
        result = _memory(mocker).search("coffee", filters={"user_id": "u1"})
        parent = _spans()[otel.OP_SEARCH]
        assert parent.kind == SpanKind.CLIENT
        assert parent.attributes[otel.GEN_AI_OPERATION_NAME] == "search_memory"
        assert parent.attributes[otel.GEN_AI_MEMORY_RECORD_COUNT] == len(result["results"])

    def test_search_emits_phase_children(self, mocker):
        _memory(mocker).search("coffee", filters={"user_id": "u1"})
        spans = _spans()
        for child_name in ("mem0.search.embed_query", "mem0.search.vector_search", "mem0.search.keyword_search"):
            assert child_name in spans, child_name
            assert spans[child_name].kind == SpanKind.INTERNAL

    def test_content_not_captured_by_default(self, mocker):
        _memory(mocker).search("secret query", filters={"user_id": "u1"})
        parent = _spans()[otel.OP_SEARCH]
        assert otel.GEN_AI_MEMORY_QUERY_TEXT not in parent.attributes
        assert otel.GEN_AI_MEMORY_RECORDS not in parent.attributes

    def test_content_captured_when_enabled(self, mocker, monkeypatch):
        monkeypatch.setenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")
        _memory(mocker).search("secret query", filters={"user_id": "u1"})
        parent = _spans()[otel.OP_SEARCH]
        assert parent.attributes[otel.GEN_AI_MEMORY_QUERY_TEXT] == "secret query"
        assert otel.GEN_AI_MEMORY_RECORDS in parent.attributes

    def test_entity_boost_span_when_entities_present(self, mocker):
        mocker.patch("mem0.memory.main.extract_entities", return_value=["Alice"])
        memory = _memory(mocker)
        memory._compute_entity_boosts = MagicMock(return_value={})
        memory.search("Alice", filters={"user_id": "u1"})
        assert "mem0.search.entity_boost" in _spans()


class TestAsyncTracing:
    @pytest.mark.asyncio
    async def test_async_add_emits_span(self, mocker):
        result = await _async_memory(mocker).add("Alice met Bob", user_id="u1")
        parent = _spans()[otel.OP_ADD]
        assert parent.attributes[otel.GEN_AI_OPERATION_NAME] == "upsert_memory"
        assert parent.attributes[otel.GEN_AI_MEMORY_RECORD_COUNT] == len(result["results"])
        assert "mem0.add.llm_extract" in _spans()

    @pytest.mark.asyncio
    async def test_async_search_emits_span(self, mocker):
        await _async_memory(mocker).search("coffee", filters={"user_id": "u1"})
        spans = _spans()
        assert spans[otel.OP_SEARCH].attributes[otel.GEN_AI_OPERATION_NAME] == "search_memory"
        assert "mem0.search.vector_search" in spans


class TestPhaseSpanErrors:
    def test_phase_span_records_error_type_and_reraises(self):
        with pytest.raises(ValueError):
            with otel.memory_phase_span("mem0.test.phase"):
                raise ValueError("boom")
        span = {s.name: s for s in _EXPORTER.get_finished_spans()}["mem0.test.phase"]
        assert span.attributes[otel.ERROR_TYPE] == "ValueError"
        assert span.status.status_code.name == "ERROR"


class TestNoopSafety:
    def test_phase_span_noop_when_unavailable(self, monkeypatch):
        monkeypatch.setattr(otel, "_OTEL_AVAILABLE", False)
        with otel.memory_phase_span("x") as span:
            assert span.is_recording() is False
        assert not _EXPORTER.get_finished_spans()

    def test_current_span_noop_when_unavailable(self, monkeypatch):
        monkeypatch.setattr(otel, "_OTEL_AVAILABLE", False)
        assert otel.current_span() is otel._NOOP_SPAN

    def test_annotate_noop_on_nonrecording_span(self):
        # Must not raise, and the records factory must not even be invoked.
        called = []
        otel.annotate_operation(
            otel._NOOP_SPAN,
            record_count=5,
            query_text="q",
            records_factory=lambda: called.append(True) or [{"content": "x"}],
        )
        assert called == []

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            (" true ", True),
            ("false", False),
            ("", False),
            ("1", False),
            ("yes", False),
        ],
    )
    def test_content_capture_env_parsing(self, monkeypatch, value, expected):
        monkeypatch.setenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", value)
        assert otel.is_content_capture_enabled() is expected

    def test_content_capture_off_when_unset(self, monkeypatch):
        monkeypatch.delenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", raising=False)
        assert otel.is_content_capture_enabled() is False
