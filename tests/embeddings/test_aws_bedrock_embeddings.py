import json
from unittest.mock import MagicMock, Mock, patch

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


@pytest.fixture
def mock_boto3_client():
    with patch("mem0.embeddings.aws_bedrock.boto3.client") as mock_client:
        mock_client.return_value = Mock()
        yield mock_client


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


def test_session_token_from_config_is_passed_to_client(mock_boto3_client):
    """A session token supplied via config must reach the bedrock-runtime client.

    Temporary credentials (STS / assume-role) require a session token; the LLM
    Bedrock provider already honors it, so the embedding provider should too.
    """
    with patch("mem0.embeddings.aws_bedrock.os.environ", {}):
        config = BaseEmbedderConfig(
            model="amazon.titan-embed-text-v2:0",
            aws_access_key_id="AKIA_TEST",
            aws_secret_access_key="SECRET_TEST",
            aws_session_token="SESSION_TOKEN_TEST",
            aws_region="eu-central-1",
        )
        AWSBedrockEmbedding(config)

    _, kwargs = mock_boto3_client.call_args
    assert kwargs["aws_session_token"] == "SESSION_TOKEN_TEST"
    assert kwargs["aws_access_key_id"] == "AKIA_TEST"
    assert kwargs["aws_secret_access_key"] == "SECRET_TEST"
    assert kwargs["region_name"] == "eu-central-1"


def test_session_token_falls_back_to_env(mock_boto3_client):
    """When config doesn't set a session token, the env var is still used."""
    with patch.dict(
        "mem0.embeddings.aws_bedrock.os.environ",
        {"AWS_SESSION_TOKEN": "ENV_SESSION_TOKEN"},
        clear=True,
    ):
        config = BaseEmbedderConfig(model="amazon.titan-embed-text-v2:0")
        AWSBedrockEmbedding(config)

    _, kwargs = mock_boto3_client.call_args
    assert kwargs["aws_session_token"] == "ENV_SESSION_TOKEN"


def test_no_session_token_passes_none(mock_boto3_client):
    """Without a token in config or env, the client receives None (unchanged)."""
    with patch("mem0.embeddings.aws_bedrock.os.environ", {}):
        config = BaseEmbedderConfig(model="amazon.titan-embed-text-v2:0")
        AWSBedrockEmbedding(config)

    _, kwargs = mock_boto3_client.call_args
    assert kwargs["aws_session_token"] is None


def _captured_request_body(mock_boto3_client, config):
    """Run a single embed call and return the JSON body sent to invoke_model."""
    runtime = mock_boto3_client.return_value
    response_stream = Mock()
    response_stream.read.return_value = json.dumps({"embedding": [0.0, 0.1, 0.2]}).encode()
    runtime.invoke_model.return_value = {"body": response_stream}

    embedder = AWSBedrockEmbedding(config)
    embedder.embed("hello world")

    _, call_kwargs = runtime.invoke_model.call_args
    return json.loads(call_kwargs["body"])


def test_titan_v2_forwards_embedding_dims_as_dimensions(mock_boto3_client):
    """Titan Text Embeddings V2 must receive embedding_dims as `dimensions`.

    Titan V2 supports an optional output size (256/512/1024); without forwarding
    it the model returns its default 1024-d vector and ignores the user's request.
    """
    with patch("mem0.embeddings.aws_bedrock.os.environ", {}):
        config = BaseEmbedderConfig(model="amazon.titan-embed-text-v2:0", embedding_dims=512)
        body = _captured_request_body(mock_boto3_client, config)

    assert body["dimensions"] == 512
    assert body["inputText"] == "hello world"


def test_titan_v2_without_embedding_dims_omits_dimensions(mock_boto3_client):
    """When embedding_dims is unset, no `dimensions` key is sent (model default)."""
    with patch("mem0.embeddings.aws_bedrock.os.environ", {}):
        config = BaseEmbedderConfig(model="amazon.titan-embed-text-v2:0")
        body = _captured_request_body(mock_boto3_client, config)

    assert "dimensions" not in body


def test_titan_v1_ignores_embedding_dims(mock_boto3_client):
    """Titan V1 has no configurable output size, so `dimensions` must not be sent."""
    with patch("mem0.embeddings.aws_bedrock.os.environ", {}):
        config = BaseEmbedderConfig(model="amazon.titan-embed-text-v1", embedding_dims=512)
        body = _captured_request_body(mock_boto3_client, config)

    assert "dimensions" not in body
