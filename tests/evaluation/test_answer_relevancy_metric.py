import numpy as np
import pytest

from embedchain.config.evaluation.base import AnswerRelevanceConfig
from embedchain.evaluation.metrics import AnswerRelevance
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
def mock_answer_relevance_metric(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test_api_key")
    monkeypatch.setenv("OPENAI_API_BASE", "test_api_base")
    metric = AnswerRelevance()
    return metric


def test_answer_relevance_init(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test_api_key")
    metric = AnswerRelevance()
    assert metric.name == EvalMetric.ANSWER_RELEVANCY.value
    assert metric.config.model == "gpt-4"
    assert metric.config.embedder == "text-embedding-ada-002"
    assert metric.config.api_key is None
    assert metric.config.num_gen_questions == 1
    monkeypatch.delenv("OPENAI_API_KEY")


def test_answer_relevance_init_with_config():
    metric = AnswerRelevance(config=AnswerRelevanceConfig(api_key="test_api_key"))
    assert metric.name == EvalMetric.ANSWER_RELEVANCY.value
    assert metric.config.model == "gpt-4"
    assert metric.config.embedder == "text-embedding-ada-002"
    assert metric.config.api_key == "test_api_key"
    assert metric.config.num_gen_questions == 1


def test_answer_relevance_init_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError):
        AnswerRelevance()


def test_generate_prompt(mock_answer_relevance_metric, mock_data):
    prompt = mock_answer_relevance_metric._generate_prompt(mock_data[0])
    assert "This is a test answer 1." in prompt

    prompt = mock_answer_relevance_metric._generate_prompt(mock_data[1])
    assert "This is a test answer 2." in prompt


def test_generate_questions(mock_answer_relevance_metric, mock_data, monkeypatch):
    monkeypatch.setattr(
        mock_answer_relevance_metric.client.chat.completions,
        "create",
        lambda model, messages: type(
            "obj",
            (object,),
            {
                "choices": [
                    type(
                        "obj",
                        (object,),
                        {"message": type("obj", (object,), {"content": "This is a test question response.\n"})},
                    )
                ]
            },
        )(),
    )
    prompt = mock_answer_relevance_metric._generate_prompt(mock_data[0])
    questions = mock_answer_relevance_metric._generate_questions(prompt)
    assert len(questions) == 1

    monkeypatch.setattr(
        mock_answer_relevance_metric.client.chat.completions,
        "create",
        lambda model, messages: type(
            "obj",
            (object,),
            {
                "choices": [
                    type("obj", (object,), {"message": type("obj", (object,), {"content": "question 1?\nquestion2?"})})
                ]
            },
        )(),
    )
    prompt = mock_answer_relevance_metric._generate_prompt(mock_data[1])
    questions = mock_answer_relevance_metric._generate_questions(prompt)
    assert len(questions) == 2


def test_generate_embedding(mock_answer_relevance_metric, mock_data, monkeypatch):
    monkeypatch.setattr(
        mock_answer_relevance_metric.client.embeddings,
        "create",
        lambda input, model: type("obj", (object,), {"data": [type("obj", (object,), {"embedding": [1, 2, 3]})]})(),
    )
    embedding = mock_answer_relevance_metric._generate_embedding("This is a test question.")
    assert len(embedding) == 3


def test_compute_similarity(mock_answer_relevance_metric, mock_data):
    original = np.array([1, 2, 3])
    generated = np.array([[1, 2, 3], [1, 2, 3]])
    similarity = mock_answer_relevance_metric._compute_similarity(original, generated)
    assert len(similarity) == 2
    assert similarity[0] == 1.0
    assert similarity[1] == 1.0


def test_compute_score(mock_answer_relevance_metric, mock_data, monkeypatch):
    monkeypatch.setattr(
        mock_answer_relevance_metric.client.chat.completions,
        "create",
        lambda model, messages: type(
            "obj",
            (object,),
            {
                "choices": [
                    type(
                        "obj",
                        (object,),
                        {"message": type("obj", (object,), {"content": "This is a test question response.\n"})},
                    )
                ]
            },
        )(),
    )
    monkeypatch.setattr(
        mock_answer_relevance_metric.client.embeddings,
        "create",
        lambda input, model: type("obj", (object,), {"data": [type("obj", (object,), {"embedding": [1, 2, 3]})]})(),
    )
    score = mock_answer_relevance_metric._compute_score(mock_data[0])
    assert score == 1.0

    monkeypatch.setattr(
        mock_answer_relevance_metric.client.chat.completions,
        "create",
        lambda model, messages: type(
            "obj",
            (object,),
            {
                "choices": [
                    type("obj", (object,), {"message": type("obj", (object,), {"content": "question 1?\nquestion2?"})})
                ]
            },
        )(),
    )
    monkeypatch.setattr(
        mock_answer_relevance_metric.client.embeddings,
        "create",
        lambda input, model: type("obj", (object,), {"data": [type("obj", (object,), {"embedding": [1, 2, 3]})]})(),
    )
    score = mock_answer_relevance_metric._compute_score(mock_data[1])
    assert score == 1.0


def test_evaluate(mock_answer_relevance_metric, mock_data, monkeypatch):
    monkeypatch.setattr(
        mock_answer_relevance_metric.client.chat.completions,
        "create",
        lambda model, messages: type(
            "obj",
            (object,),
            {
                "choices": [
                    type(
                        "obj",
                        (object,),
                        {"message": type("obj", (object,), {"content": "This is a test question response.\n"})},
                    )
                ]
            },
        )(),
    )
    monkeypatch.setattr(
        mock_answer_relevance_metric.client.embeddings,
        "create",
        lambda input, model: type("obj", (object,), {"data": [type("obj", (object,), {"embedding": [1, 2, 3]})]})(),
    )
    score = mock_answer_relevance_metric.evaluate(mock_data)
    assert score == 1.0

    monkeypatch.setattr(
        mock_answer_relevance_metric.client.chat.completions,
        "create",
        lambda model, messages: type(
            "obj",
            (object,),
            {
                "choices": [
                    type("obj", (object,), {"message": type("obj", (object,), {"content": "question 1?\nquestion2?"})})
                ]
            },
        )(),
    )
    monkeypatch.setattr(
        mock_answer_relevance_metric.client.embeddings,
        "create",
        lambda input, model: type("obj", (object,), {"data": [type("obj", (object,), {"embedding": [1, 2, 3]})]})(),
    )
    score = mock_answer_relevance_metric.evaluate(mock_data)
    assert score == 1.0
