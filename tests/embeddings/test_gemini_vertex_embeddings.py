from unittest.mock import patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.gemini import GoogleGenAIEmbedding

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

    mock_client_class.assert_called_once_with(vertexai=True, project="my-project", location="europe-west4")


def test_vertexai_enabled_from_environment(monkeypatch, mock_client_class):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-east1")

    GoogleGenAIEmbedding(BaseEmbedderConfig())

    mock_client_class.assert_called_once_with(vertexai=True, project="env-project", location="us-east1")


def test_vertexai_location_defaults_when_env_absent(monkeypatch, mock_client_class):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "1")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")

    GoogleGenAIEmbedding(BaseEmbedderConfig())

    mock_client_class.assert_called_once_with(vertexai=True, project="env-project", location="us-central1")


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
    config = BaseEmbedderConfig(vertexai=True, project="p", model="models/text-embedding-005")

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
