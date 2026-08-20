from unittest.mock import ANY, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.gemini import GoogleGenAIEmbedding


@pytest.fixture
def mock_genai():
    with patch("mem0.embeddings.gemini.genai.Client") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.models.embed_content.return_value = None
        yield mock_client.models.embed_content


@pytest.fixture
def config():
    return BaseEmbedderConfig(api_key="dummy_api_key", model="test_model", embedding_dims=786)


def test_embed_query(mock_genai, config):
    mock_embedding_response = type(
        "Response", (), {"embeddings": [type("Embedding", (), {"values": [0.1, 0.2, 0.3, 0.4]})]}
    )()
    mock_genai.return_value = mock_embedding_response

    embedder = GoogleGenAIEmbedding(config)

    text = "Hello, world!"
    embedding = embedder.embed(text)

    assert embedding == [0.1, 0.2, 0.3, 0.4]
    mock_genai.assert_called_once_with(model="test_model", contents="Hello, world!", config=ANY)


def test_embed_returns_empty_list_if_none(mock_genai, config):
    mock_genai.return_value = type("Response", (), {"embeddings": [type("Embedding", (), {"values": []})]})()

    embedder = GoogleGenAIEmbedding(config)

    result = embedder.embed("test")
    assert result == []


def test_embed_raises_on_error(mock_genai, config):
    mock_genai.side_effect = RuntimeError("Embedding failed")

    embedder = GoogleGenAIEmbedding(config)

    with pytest.raises(RuntimeError, match="Embedding failed"):
        embedder.embed("some input")


def test_config_initialization(config):
    embedder = GoogleGenAIEmbedding(config)

    assert embedder.config.api_key == "dummy_api_key"
    assert embedder.config.model == "test_model"
    assert embedder.config.embedding_dims == 786


def test_embed_batch_single_call(mock_genai, config):
    emb0 = type("Embedding", (), {"values": [0.1, 0.2, 0.3]})()
    emb1 = type("Embedding", (), {"values": [0.4, 0.5, 0.6]})()
    mock_genai.return_value = type("Response", (), {"embeddings": [emb0, emb1]})()

    embedder = GoogleGenAIEmbedding(config)

    texts = ["First text.", "Second text."]
    result = embedder.embed_batch(texts)

    mock_genai.assert_called_once_with(model="test_model", contents=texts, config=ANY)
    assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


def test_embed_batch_empty_list(mock_genai, config):
    embedder = GoogleGenAIEmbedding(config)

    result = embedder.embed_batch([])

    assert result == []
    mock_genai.assert_not_called()


def test_embed_batch_count_mismatch_raises(mock_genai, config):
    emb0 = type("Embedding", (), {"values": [0.1, 0.2, 0.3]})()
    mock_genai.return_value = type("Response", (), {"embeddings": [emb0]})()

    embedder = GoogleGenAIEmbedding(config)

    with pytest.raises(ValueError, match="returned 1 embeddings for 2 texts"):
        embedder.embed_batch(["first text", "second text"])


def test_embed_batch_chunks_over_100_texts(mock_genai, config):
    def make_chunk_response(**kwargs):
        chunk = kwargs["contents"]
        emb = type("Embedding", (), {"values": [0.1, 0.2]})
        return type("Response", (), {"embeddings": [emb() for _ in chunk]})()

    mock_genai.side_effect = make_chunk_response

    embedder = GoogleGenAIEmbedding(config)
    texts = [f"text {i}" for i in range(150)]
    result = embedder.embed_batch(texts)

    assert mock_genai.call_count == 2
    assert len(result) == 150


def test_embed_batch_strips_newlines(mock_genai, config):
    emb0 = type("Embedding", (), {"values": [0.1, 0.2, 0.3]})()
    mock_genai.return_value = type("Response", (), {"embeddings": [emb0]})()

    embedder = GoogleGenAIEmbedding(config)
    embedder.embed_batch(["line one\nline two"])

    mock_genai.assert_called_once_with(model="test_model", contents=["line one line two"], config=ANY)


# ---------------------------------------------------------------------------
# Backend selection: Gemini Developer API vs Vertex AI
#
# The Gemini *LLM* has honoured Vertex AI since GeminiConfig gained
# vertexai/project/location (defaulted from GOOGLE_GENAI_USE_VERTEXAI /
# GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION). The embedder used the same
# SDK but always constructed genai.Client(api_key=...), so a deployment with
# mem0's Gemini LLM on Vertex still had to supply a GOOGLE_API_KEY purely for
# embeddings. These tests pin the embedder to the same contract as the LLM.
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client_class():
    with patch("mem0.embeddings.gemini.genai.Client") as mock_cls:
        yield mock_cls


@pytest.fixture(autouse=True)
def clear_google_env(monkeypatch):
    """Backend selection reads the environment, so isolate it per test."""
    for var in (
        "GOOGLE_GENAI_USE_VERTEXAI",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
        "GOOGLE_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)


def test_defaults_to_developer_api_client(mock_client_class):
    GoogleGenAIEmbedding(BaseEmbedderConfig(api_key="dummy_api_key"))

    mock_client_class.assert_called_once_with(api_key="dummy_api_key")


def test_default_model_keeps_models_prefix_on_developer_api(mock_client_class):
    embedder = GoogleGenAIEmbedding(BaseEmbedderConfig(api_key="dummy_api_key"))

    assert embedder.config.model == "models/gemini-embedding-001"


def test_vertexai_config_builds_vertex_client(mock_client_class):
    config = BaseEmbedderConfig(vertexai=True, project="my-project", location="europe-west4")

    GoogleGenAIEmbedding(config)

    mock_client_class.assert_called_once_with(
        vertexai=True, project="my-project", location="europe-west4"
    )


def test_vertexai_enabled_from_environment(monkeypatch, mock_client_class):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-east1")

    GoogleGenAIEmbedding(BaseEmbedderConfig())

    mock_client_class.assert_called_once_with(
        vertexai=True, project="env-project", location="us-east1"
    )


def test_vertexai_location_defaults_when_env_absent(monkeypatch, mock_client_class):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "1")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")

    GoogleGenAIEmbedding(BaseEmbedderConfig())

    mock_client_class.assert_called_once_with(
        vertexai=True, project="env-project", location="us-central1"
    )


def test_explicit_vertexai_false_overrides_environment(monkeypatch, mock_client_class):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")

    GoogleGenAIEmbedding(BaseEmbedderConfig(vertexai=False, api_key="dummy_api_key"))

    mock_client_class.assert_called_once_with(api_key="dummy_api_key")


def test_vertexai_strips_models_prefix_from_default_model(mock_client_class):
    """Vertex publisher model IDs are unprefixed.

    Vertex answers a "models/"-prefixed ID with an empty-bodied 404, so the
    Developer-API default must be normalised rather than passed through.
    """
    embedder = GoogleGenAIEmbedding(BaseEmbedderConfig(vertexai=True, project="p"))

    assert embedder.config.model == "gemini-embedding-001"


def test_vertexai_strips_models_prefix_from_explicit_model(mock_client_class):
    config = BaseEmbedderConfig(
        vertexai=True, project="p", model="models/text-embedding-005"
    )

    embedder = GoogleGenAIEmbedding(config)

    assert embedder.config.model == "text-embedding-005"


def test_vertexai_leaves_unprefixed_model_untouched(mock_client_class):
    config = BaseEmbedderConfig(vertexai=True, project="p", model="gemini-embedding-001")

    embedder = GoogleGenAIEmbedding(config)

    assert embedder.config.model == "gemini-embedding-001"


def test_vertexai_client_receives_no_api_key(monkeypatch, mock_client_class):
    """Vertex auth is ADC; an api_key would switch the SDK to Express mode.

    google-genai routes to the Vertex Express endpoints when it is given an API
    key, and the regular Vertex prediction endpoints reject those credentials.
    Passing the key through would therefore break the ADC path for anyone who
    happens to also have GOOGLE_API_KEY set.
    """
    monkeypatch.setenv("GOOGLE_API_KEY", "leftover-key")

    GoogleGenAIEmbedding(BaseEmbedderConfig(vertexai=True, project="p", location="us-central1"))

    _, kwargs = mock_client_class.call_args
    assert "api_key" not in kwargs
