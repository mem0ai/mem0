"""Tests for the embedding-failure taxonomy: partial-failure surfacing,
error_class assignment at the point of detection, and the validation check
that keeps NaN/Inf/wrong-dim vectors out of the store (#5245)."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mem0.exceptions import EmbeddingError, EmbeddingErrorClass
from mem0.memory.main import Memory, _validate_embedding


# --------------------------------------------------------------------------- #
# _validate_embedding — the validation_error detection point (pure function)
# --------------------------------------------------------------------------- #
def test_validate_embedding_accepts_clean_vector():
    assert _validate_embedding([0.1, 0.2, 0.3], 3) is None


def test_validate_embedding_rejects_nan():
    assert _validate_embedding([float("nan"), 0.2, 0.3], 3) is not None


def test_validate_embedding_rejects_inf():
    assert _validate_embedding([float("inf"), 0.2, 0.3], 3) is not None


def test_validate_embedding_rejects_wrong_dimension():
    assert _validate_embedding([0.1, 0.2], 3) is not None


def test_validate_embedding_skips_dim_when_unconfigured_but_keeps_finiteness():
    assert _validate_embedding([0.1, 0.2, 0.3, 0.4], None) is None
    assert _validate_embedding([float("inf"), 0.2], None) is not None


def test_validate_embedding_rejects_empty():
    assert _validate_embedding([], 3) is not None


def test_validate_embedding_rejects_complex_without_crashing():
    # math.isfinite raises TypeError on complex; the check must reject, not crash.
    assert _validate_embedding([1 + 2j, 0.2, 0.3], 3) is not None


def test_validate_embedding_first_vector_sets_batch_dimension(mocker):
    """Order-dependence guard: a wrong-length first vector poisons the batch
    reference (documented trade-off). Pin the behavior so it can't change silently."""
    # First accepted vector defines the batch dimension; a later differing length fails.
    def embed(text):
        return [0.1, 0.2, 0.3] if text == "first" else [0.1, 0.2]

    m = _make_memory(mocker, ["first", "second"], embed)
    failed = []
    results = _run(m, failed)
    assert [r["memory"] for r in results] == ["first"]
    assert failed[0]["text"] == "second"
    assert failed[0]["error_class"] == EmbeddingErrorClass.VALIDATION


# --------------------------------------------------------------------------- #
# Integration: _add_to_vector_store collects failures with error_class while
# preserving the successes (the out-parameter `failed`).
# --------------------------------------------------------------------------- #
def _make_memory(mocker, extracted_texts, embed_fn):
    """A Memory whose LLM extracts `extracted_texts` and whose embedder runs
    `embed_fn(text)` per item (batch endpoint forced to fail -> per-item path)."""
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mocker.MagicMock())
    mock_vs = mocker.MagicMock()
    mock_vs.return_value.search.return_value = []
    mocker.patch(
        "mem0.utils.factory.VectorStoreFactory.create",
        side_effect=[mock_vs.return_value, mocker.MagicMock()],
    )
    mocker.patch("mem0.utils.factory.LlmFactory.create", mocker.MagicMock())
    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())
    mocker.patch("mem0.memory.main.extract_entities_batch", side_effect=lambda texts: [[] for _ in texts])
    mocker.patch("mem0.memory.main.capture_event")
    # patches so the add() wrapper is drivable too
    mocker.patch("mem0.memory.main.parse_vision_messages", side_effect=lambda messages, *a, **k: messages)
    mocker.patch("mem0.memory.main.detect_temporal_usage_from_metadata", return_value=None)
    mocker.patch("mem0.memory.main.detect_scale_threshold_from_add_result", return_value=None)
    mocker.patch("mem0.memory.main.display_first_run_notice")
    mocker.patch("mem0.memory.main._build_filters_and_metadata", return_value=({}, {}))

    m = Memory()
    m.config = mocker.MagicMock()
    m.config.custom_instructions = None
    m.custom_instructions = None
    m.api_version = "v1.1"
    m.db.get_last_messages = MagicMock(return_value=[])
    m.db.save_messages = MagicMock()
    m.llm.generate_response = MagicMock(
        return_value=json.dumps({"memory": [{"text": t} for t in extracted_texts]})
    )
    m.embedding_model.embed_batch = MagicMock(side_effect=Exception("batch endpoint down"))
    m.embedding_model.embed = MagicMock(side_effect=lambda text, action="add": embed_fn(text))
    m.embedding_model.config = SimpleNamespace(embedding_dims=3)
    return m


def _run(m, failed):
    return m._add_to_vector_store(
        messages=[{"role": "user", "content": "x"}], metadata={}, filters={}, infer=True, failed=failed
    )


def test_provider_error_collected_and_not_persisted(mocker):
    def embed(text):
        if text == "bad":
            raise RuntimeError("OpenAI 503")
        return [0.1, 0.2, 0.3]

    m = _make_memory(mocker, ["good", "bad"], embed)
    failed = []
    results = _run(m, failed)

    assert [r["memory"] for r in results] == ["good"]
    assert len(failed) == 1
    assert failed[0]["text"] == "bad"
    assert failed[0]["error_class"] == EmbeddingErrorClass.PROVIDER


def test_validation_error_nan_not_persisted(mocker):
    def embed(text):
        if text == "bad":
            return [float("nan"), 0.2, 0.3]
        return [0.1, 0.2, 0.3]

    m = _make_memory(mocker, ["good", "bad"], embed)
    failed = []
    results = _run(m, failed)

    assert [r["memory"] for r in results] == ["good"]
    assert failed[0]["text"] == "bad"
    assert failed[0]["error_class"] == EmbeddingErrorClass.VALIDATION


def test_validation_error_wrong_dimension(mocker):
    def embed(text):
        if text == "bad":
            return [0.1, 0.2]  # dim 2 != configured 3
        return [0.1, 0.2, 0.3]

    m = _make_memory(mocker, ["good", "bad"], embed)
    failed = []
    _run(m, failed)
    assert failed[0]["error_class"] == EmbeddingErrorClass.VALIDATION


def test_two_classes_in_one_batch(mocker):
    """The conflation guard: provider and validation must surface distinctly."""
    def embed(text):
        if text == "prov":
            raise RuntimeError("503")
        if text == "val":
            return [float("inf"), 0.2, 0.3]
        return [0.1, 0.2, 0.3]

    m = _make_memory(mocker, ["good", "prov", "val"], embed)
    failed = []
    results = _run(m, failed)

    assert [r["memory"] for r in results] == ["good"]
    by_text = {f["text"]: f["error_class"] for f in failed}
    assert by_text == {
        "prov": EmbeddingErrorClass.PROVIDER,
        "val": EmbeddingErrorClass.VALIDATION,
    }


def test_all_clean_yields_no_failures(mocker):
    m = _make_memory(mocker, ["a", "b"], lambda text: [0.1, 0.2, 0.3])
    failed = []
    results = _run(m, failed)
    assert [r["memory"] for r in results] == ["a", "b"]
    assert failed == []


# --------------------------------------------------------------------------- #
# add() wrapper: additive `failed` key by default; opt-in raise.
# --------------------------------------------------------------------------- #
def test_add_returns_failed_in_result_by_default(mocker):
    def embed(text):
        if text == "bad":
            raise RuntimeError("503")
        return [0.1, 0.2, 0.3]

    m = _make_memory(mocker, ["good", "bad"], embed)
    res = m.add("hello", user_id="u")
    assert [r["memory"] for r in res["results"]] == ["good"]
    assert len(res["failed"]) == 1
    assert res["failed"][0]["error_class"] == EmbeddingErrorClass.PROVIDER


def test_add_raise_on_partial_failure_raises(mocker):
    def embed(text):
        if text == "bad":
            raise RuntimeError("503")
        return [0.1, 0.2, 0.3]

    m = _make_memory(mocker, ["good", "bad"], embed)
    with pytest.raises(EmbeddingError):
        m.add("hello", user_id="u", raise_on_partial_failure=True)


# --------------------------------------------------------------------------- #
# Regressions caught in review: numpy embedders, and short-batch tail.
# --------------------------------------------------------------------------- #
def test_validate_embedding_accepts_numpy_array():
    np = pytest.importorskip("numpy")
    assert _validate_embedding(np.array([0.1, 0.2, 0.3], dtype=np.float32), 3) is None
    assert _validate_embedding(np.array([np.nan, 0.2, 0.3], dtype=np.float32), 3) is not None


def test_batch_returning_fewer_vectors_surfaces_tail(mocker):
    """A batch that returns fewer vectors than inputs must surface the tail,
    not silently drop it (the original #5245 failure mode)."""
    m = _make_memory(mocker, ["a", "b"], lambda text: [0.1, 0.2, 0.3])
    m.embedding_model.embed_batch = MagicMock(return_value=[[0.1, 0.2, 0.3]])  # 1 vector for 2 texts
    failed = []
    results = _run(m, failed)
    assert [r["memory"] for r in results] == ["a"]
    assert len(failed) == 1
    assert failed[0]["text"] == "b"
    assert failed[0]["error_class"] == EmbeddingErrorClass.PROVIDER


# --------------------------------------------------------------------------- #
# Async parity: the same collection happens on the async add() path.
# --------------------------------------------------------------------------- #
def _make_async_memory(mocker, extracted_texts, embed_fn):
    from mem0.memory.main import AsyncMemory

    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mocker.MagicMock())
    mock_vs = mocker.MagicMock()
    mock_vs.return_value.search.return_value = []
    mocker.patch(
        "mem0.utils.factory.VectorStoreFactory.create",
        side_effect=[mock_vs.return_value, mocker.MagicMock()],
    )
    mocker.patch("mem0.utils.factory.LlmFactory.create", mocker.MagicMock())
    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())
    mocker.patch("mem0.memory.main.extract_entities_batch", side_effect=lambda texts: [[] for _ in texts])
    mocker.patch("mem0.memory.main.capture_event")

    m = AsyncMemory()
    m.config = mocker.MagicMock()
    m.config.custom_instructions = None
    m.custom_instructions = None
    m.api_version = "v1.1"
    m.db.get_last_messages = MagicMock(return_value=[])
    m.db.save_messages = MagicMock()
    m.llm.generate_response = MagicMock(
        return_value=json.dumps({"memory": [{"text": t} for t in extracted_texts]})
    )
    m.embedding_model.embed_batch = MagicMock(side_effect=Exception("batch endpoint down"))
    m.embedding_model.embed = MagicMock(side_effect=lambda text, action="add": embed_fn(text))
    m.embedding_model.config = SimpleNamespace(embedding_dims=3)
    return m


@pytest.mark.asyncio
async def test_async_provider_and_validation_collected(mocker):
    def embed(text):
        if text == "prov":
            raise RuntimeError("503")
        if text == "val":
            return [float("nan"), 0.2, 0.3]
        return [0.1, 0.2, 0.3]

    m = _make_async_memory(mocker, ["good", "prov", "val"], embed)
    failed = []
    results = await m._add_to_vector_store(
        messages=[{"role": "user", "content": "x"}], metadata={}, effective_filters={}, infer=True, failed=failed
    )
    assert [r["memory"] for r in results] == ["good"]
    by_text = {f["text"]: f["error_class"] for f in failed}
    assert by_text == {
        "prov": EmbeddingErrorClass.PROVIDER,
        "val": EmbeddingErrorClass.VALIDATION,
    }
