import pytest

from embedchain.config.evaluation.base import ContextRelevanceConfig
from embedchain.evaluation.metrics import ContextRelevance
from embedchain.utils.evaluation import EvalData, EvalMetric


@pytest.fixture
def mock_data():
    return [
        EvalData(
            contexts=[
                "This is a test context 1.",
            ],
            question="This is a test question 1.",
            answer="This is a test answer 1.",
        ),
        EvalData(
            contexts=[
                "This is a test context 2-1.",
                "This is a test context 2-2.",
            ],
            question="This is a test question 2.",
            answer="This is a test answer 2.",
        ),
    ]


@pytest.fixture
def mock_context_relevance_metric(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test_api_key")
    metric = ContextRelevance()
    return metric


def test_context_relevance_init(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test_api_key")
    metric = ContextRelevance()
    assert metric.name == EvalMetric.CONTEXT_RELEVANCY.value
    assert metric.config.model == "gpt-4"
    assert metric.config.api_key is None
    assert metric.config.language == "en"
    monkeypatch.delenv("OPENAI_API_KEY")


def test_context_relevance_init_with_config():
    metric = ContextRelevance(config=ContextRelevanceConfig(api_key="test_api_key"))
    assert metric.name == EvalMetric.CONTEXT_RELEVANCY.value
    assert metric.config.model == "gpt-4"
    assert metric.config.api_key == "test_api_key"
    assert metric.config.language == "en"


def test_context_relevance_init_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError):
        ContextRelevance()


def test_sentence_segmenter(mock_context_relevance_metric):
    text = "This is a test sentence. This is another sentence."
    assert mock_context_relevance_metric._sentence_segmenter(text) == [
        "This is a test sentence. ",
        "This is another sentence.",
    ]


def test_compute_score(mock_context_relevance_metric, mock_data, monkeypatch):
    monkeypatch.setattr(
        mock_context_relevance_metric.client.chat.completions,
        "create",
        lambda model, messages: type(
            "obj",
            (object,),
            {
                "choices": [
                    type("obj", (object,), {"message": type("obj", (object,), {"content": "This is a test reponse."})})
                ]
            },
        )(),
    )
    assert mock_context_relevance_metric._compute_score(mock_data[0]) == 1.0
    assert mock_context_relevance_metric._compute_score(mock_data[1]) == 0.5


def test_evaluate(mock_context_relevance_metric, mock_data, monkeypatch):
    monkeypatch.setattr(
        mock_context_relevance_metric.client.chat.completions,
        "create",
        lambda model, messages: type(
            "obj",
            (object,),
            {
                "choices": [
                    type("obj", (object,), {"message": type("obj", (object,), {"content": "This is a test reponse."})})
                ]
            },
        )(),
    )
    assert mock_context_relevance_metric.evaluate(mock_data) == 0.75
