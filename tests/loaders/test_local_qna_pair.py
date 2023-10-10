import hashlib

import pytest

from embedchain.loaders.local_qna_pair import LocalQnaPairLoader


@pytest.fixture
def qna_pair_loader():
    return LocalQnaPairLoader()


def test_load_data(qna_pair_loader):
    question = "What is the capital of France?"
    answer = "The capital of France is Paris."

    content = (question, answer)
    result = qna_pair_loader.load_data(content)

    assert "doc_id" in result
    assert "data" in result
    url = "local"

    expected_content = f"Q: {question}\nA: {answer}"
    assert result["data"][0]["content"] == expected_content

    assert result["data"][0]["meta_data"]["url"] == url

    assert result["data"][0]["meta_data"]["question"] == question

    expected_doc_id = hashlib.sha256((expected_content + url).encode()).hexdigest()
    assert result["doc_id"] == expected_doc_id
