import numpy as np
import pytest

from embedchain.config.evaluation.base import GroundednessConfig
from embedchain.evaluation.metrics import Groundedness
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
def mock_groundedness_metric(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test_api_key")
    metric = Groundedness()
    return metric


def test_groundedness_init(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test_api_key")
    metric = Groundedness()
    assert metric.name == EvalMetric.GROUNDEDNESS.value
    assert metric.config.model == "gpt-4"
    assert metric.config.api_key is None
    monkeypatch.delenv("OPENAI_API_KEY")


def test_groundedness_init_with_config():
    metric = Groundedness(config=GroundednessConfig(api_key="test_api_key"))
    assert metric.name == EvalMetric.GROUNDEDNESS.value
    assert metric.config.model == "gpt-4"
    assert metric.config.api_key == "test_api_key"


def test_groundedness_init_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError):
        Groundedness()


def test_generate_answer_claim_prompt(mock_groundedness_metric, mock_data):
    prompt = mock_groundedness_metric._generate_answer_claim_prompt(data=mock_data[0])
    assert "This is a test question 1." in prompt
    assert "This is a test answer 1." in prompt


def test_get_claim_statements(mock_groundedness_metric, mock_data, monkeypatch):
    monkeypatch.setattr(
        mock_groundedness_metric.client.chat.completions,
        "create",
        lambda *args, **kwargs: type(
            "obj",
            (object,),
            {
                "choices": [
                    type(
                        "obj",
                        (object,),
                        {
                            "message": type(
                                "obj",
                                (object,),
                                {
                                    "content": """This is a test answer 1.
                                                                                        This is a test answer 2.
                                                                                        This is a test answer 3."""
                                },
                            )
                        },
                    )
                ]
            },
        )(),
    )
    prompt = mock_groundedness_metric._generate_answer_claim_prompt(data=mock_data[0])
    claim_statements = mock_groundedness_metric._get_claim_statements(prompt=prompt)
    assert len(claim_statements) == 3
    assert "This is a test answer 1." in claim_statements


def test_generate_claim_inference_prompt(mock_groundedness_metric, mock_data):
    prompt = mock_groundedness_metric._generate_answer_claim_prompt(data=mock_data[0])
    claim_statements = [
        "This is a test claim 1.",
        "This is a test claim 2.",
    ]
    prompt = mock_groundedness_metric._generate_claim_inference_prompt(
        data=mock_data[0], claim_statements=claim_statements
    )
    assert "This is a test context 1." in prompt
    assert "This is a test claim 1." in prompt


def test_get_claim_verdict_scores(mock_groundedness_metric, mock_data, monkeypatch):
    monkeypatch.setattr(
        mock_groundedness_metric.client.chat.completions,
        "create",
        lambda *args, **kwargs: type(
            "obj",
            (object,),
            {"choices": [type("obj", (object,), {"message": type("obj", (object,), {"content": "1\n0\n-1"})})]},
        )(),
    )
    prompt = mock_groundedness_metric._generate_answer_claim_prompt(data=mock_data[0])
    claim_statements = mock_groundedness_metric._get_claim_statements(prompt=prompt)
    prompt = mock_groundedness_metric._generate_claim_inference_prompt(
        data=mock_data[0], claim_statements=claim_statements
    )
    claim_verdict_scores = mock_groundedness_metric._get_claim_verdict_scores(prompt=prompt)
    assert len(claim_verdict_scores) == 3
    assert claim_verdict_scores[0] == 1
    assert claim_verdict_scores[1] == 0


def test_compute_score(mock_groundedness_metric, mock_data, monkeypatch):
    monkeypatch.setattr(
        mock_groundedness_metric,
        "_get_claim_statements",
        lambda *args, **kwargs: np.array(
            [
                "This is a test claim 1.",
                "This is a test claim 2.",
            ]
        ),
    )
    monkeypatch.setattr(mock_groundedness_metric, "_get_claim_verdict_scores", lambda *args, **kwargs: np.array([1, 0]))
    score = mock_groundedness_metric._compute_score(data=mock_data[0])
    assert score == 0.5


def test_evaluate(mock_groundedness_metric, mock_data, monkeypatch):
    monkeypatch.setattr(mock_groundedness_metric, "_compute_score", lambda *args, **kwargs: 0.5)
    score = mock_groundedness_metric.evaluate(dataset=mock_data)
    assert score == 0.5
