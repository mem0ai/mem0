import json
from unittest.mock import MagicMock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.aws_bedrock import AWSBedrockEmbedding


@pytest.fixture
def mock_boto3():
    """Patch boto3 so no real AWS calls are made during unit tests."""
    with patch("mem0.embeddings.aws_bedrock.boto3") as mock_b3:
        runtime_client = MagicMock()
        mock_b3.client.return_value = runtime_client
        yield runtime_client


def _make_embedder(model, mock_boto3):
    return AWSBedrockEmbedding(BaseEmbedderConfig(model=model))


def _set_response(mock_boto3, body):
    response_body = MagicMock()
    response_body.read.return_value = json.dumps(body).encode("utf-8")
    mock_boto3.invoke_model.return_value = {"body": response_body}


def _sent_body(mock_boto3):
    """Return the request body dict passed to invoke_model."""
    _, kwargs = mock_boto3.invoke_model.call_args
    return json.loads(kwargs["body"])


def test_titan_embed_uses_input_text(mock_boto3):
    embedder = _make_embedder("amazon.titan-embed-text-v1", mock_boto3)
    _set_response(mock_boto3, {"embedding": [0.1, 0.2, 0.3]})

    result = embedder.embed("hello world", memory_action="add")

    assert result == [0.1, 0.2, 0.3]
    body = _sent_body(mock_boto3)
    assert body == {"inputText": "hello world"}


def test_cohere_add_uses_search_document_input_type(mock_boto3):
    embedder = _make_embedder("cohere.embed-english-v3", mock_boto3)
    _set_response(mock_boto3, {"embeddings": [[0.4, 0.5, 0.6]]})

    result = embedder.embed("a stored document", memory_action="add")

    assert result == [0.4, 0.5, 0.6]
    body = _sent_body(mock_boto3)
    assert body["texts"] == ["a stored document"]
    assert body["input_type"] == "search_document"


def test_cohere_update_uses_search_document_input_type(mock_boto3):
    embedder = _make_embedder("cohere.embed-english-v3", mock_boto3)
    _set_response(mock_boto3, {"embeddings": [[0.4, 0.5, 0.6]]})

    embedder.embed("an updated document", memory_action="update")

    assert _sent_body(mock_boto3)["input_type"] == "search_document"


def test_cohere_search_uses_search_query_input_type(mock_boto3):
    """A query must be embedded with Cohere's asymmetric ``search_query`` type.

    Cohere v3 embeddings are asymmetric: documents are stored with
    ``search_document`` and queries are encoded with ``search_query``. Using
    ``search_document`` for queries produces a vector from the wrong projection
    and degrades retrieval. mem0 passes ``memory_action="search"`` for queries,
    so the Bedrock embedder must honor it.
    """
    embedder = _make_embedder("cohere.embed-english-v3", mock_boto3)
    _set_response(mock_boto3, {"embeddings": [[0.7, 0.8, 0.9]]})

    result = embedder.embed("what does the user like?", memory_action="search")

    assert result == [0.7, 0.8, 0.9]
    body = _sent_body(mock_boto3)
    assert body["texts"] == ["what does the user like?"]
    assert body["input_type"] == "search_query"


def test_cohere_default_action_uses_search_document_input_type(mock_boto3):
    """With no memory_action, default to the document side (backward compatible)."""
    embedder = _make_embedder("cohere.embed-english-v3", mock_boto3)
    _set_response(mock_boto3, {"embeddings": [[0.1, 0.1, 0.1]]})

    embedder.embed("some text")

    assert _sent_body(mock_boto3)["input_type"] == "search_document"
