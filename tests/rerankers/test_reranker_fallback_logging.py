import logging
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mem0.configs.rerankers.cohere import CohereRerankerConfig
from mem0.configs.rerankers.zero_entropy import ZeroEntropyRerankerConfig


LOGGER_NAME = "mem0.reranker.base"


@pytest.fixture
def mock_cohere(monkeypatch):
    fake_cohere = ModuleType("cohere")
    fake_client = MagicMock()
    fake_cohere.Client = MagicMock(return_value=fake_client)
    monkeypatch.setitem(sys.modules, "cohere", fake_cohere)

    import mem0.reranker.cohere_reranker as cohere_reranker

    monkeypatch.setattr(cohere_reranker, "cohere", fake_cohere, raising=False)
    monkeypatch.setattr(cohere_reranker, "COHERE_AVAILABLE", True, raising=False)
    return cohere_reranker, fake_client


@pytest.fixture
def mock_zero_entropy(monkeypatch):
    fake_module = ModuleType("zeroentropy")
    fake_client = MagicMock()
    fake_module.ZeroEntropy = MagicMock(return_value=fake_client)
    monkeypatch.setitem(sys.modules, "zeroentropy", fake_module)

    import mem0.reranker.zero_entropy_reranker as zero_entropy_reranker

    monkeypatch.setattr(zero_entropy_reranker, "ZeroEntropy", fake_module.ZeroEntropy, raising=False)
    monkeypatch.setattr(zero_entropy_reranker, "ZERO_ENTROPY_AVAILABLE", True, raising=False)
    return zero_entropy_reranker, fake_client


def _docs():
    return [{"memory": "doc0"}, {"memory": "doc1"}]


def _assert_fallback_warning(caplog, provider):
    assert any(
        record.levelno == logging.WARNING
        and provider in record.getMessage()
        and "returning fallback rerank scores" in record.getMessage()
        for record in caplog.records
    )


def test_cohere_fallback_logs_warning(caplog, mock_cohere):
    module, fake_client = mock_cohere
    fake_client.rerank.side_effect = RuntimeError("cohere down")

    reranker = module.CohereReranker(CohereRerankerConfig(api_key="test-key"))
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        result = reranker.rerank("query", _docs())

    _assert_fallback_warning(caplog, "CohereReranker")
    assert [doc["rerank_score"] for doc in result] == [0.0, 0.0]


def test_zero_entropy_fallback_logs_warning(caplog, mock_zero_entropy):
    module, fake_client = mock_zero_entropy
    fake_client.models.rerank.side_effect = RuntimeError("zero entropy down")

    reranker = module.ZeroEntropyReranker(ZeroEntropyRerankerConfig(api_key="test-key"))
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        result = reranker.rerank("query", _docs())

    _assert_fallback_warning(caplog, "ZeroEntropyReranker")
    assert [doc["rerank_score"] for doc in result] == [0.0, 0.0]


def test_huggingface_fallback_logs_warning(caplog):
    from mem0.reranker.huggingface_reranker import HuggingFaceReranker

    reranker = object.__new__(HuggingFaceReranker)
    reranker.config = SimpleNamespace(batch_size=32, max_length=512, normalize=True, top_k=None)
    reranker.device = "cpu"
    reranker.tokenizer = MagicMock(side_effect=RuntimeError("tokenizer failed"))

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        result = reranker.rerank("query", _docs())

    _assert_fallback_warning(caplog, "HuggingFaceReranker")
    assert [doc["rerank_score"] for doc in result] == [0.0, 0.0]


def test_sentence_transformer_fallback_logs_warning(caplog):
    from mem0.reranker.sentence_transformer_reranker import SentenceTransformerReranker

    reranker = object.__new__(SentenceTransformerReranker)
    reranker.config = SimpleNamespace(batch_size=32, show_progress_bar=False, top_k=None)
    reranker.model = MagicMock()
    reranker.model.predict.side_effect = RuntimeError("predict failed")

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        result = reranker.rerank("query", _docs())

    _assert_fallback_warning(caplog, "SentenceTransformerReranker")
    assert [doc["rerank_score"] for doc in result] == [0.0, 0.0]


def test_llm_fallback_logs_warning(caplog, mock_llm):
    from mem0.reranker.llm_reranker import LLMReranker

    _, mock_llm_instance = mock_llm
    mock_llm_instance.generate_response.side_effect = RuntimeError("llm down")

    reranker = LLMReranker({"provider": "openai"})
    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        result = reranker.rerank("query", [{"memory": "doc"}])

    _assert_fallback_warning(caplog, "LLMReranker")
    assert result[0]["rerank_score"] == 0.5
