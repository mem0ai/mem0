"""Tests for the config router's default configuration and schema round-trips.

The default configuration seeds the persistent DB config row via
get-or-create on every /api/v1/config GET, and the DB row overrides
environment configuration in get_memory_client() — so these defaults must
honor the documented LLM_* / EMBEDDER_* environment variables, and the
pydantic schemas must not silently drop fields on PUT round-trips.
"""

import os

# Set dummy keys before any imports that trigger client initialization
os.environ.setdefault("OPENAI_API_KEY", "test-key")

from unittest import mock

from app.routers.config import ConfigSchema, get_default_configuration

# ---------------------------------------------------------------------------
# get_default_configuration
# ---------------------------------------------------------------------------

def test_defaults_unchanged_without_env_vars():
    """With no LLM_*/EMBEDDER_* env vars set, output matches the legacy hardcoded defaults."""
    with mock.patch.dict(os.environ, {}, clear=True):
        config = get_default_configuration()

    assert config["mem0"]["llm"] == {
        "provider": "openai",
        "config": {
            "model": "gpt-4o-mini",
            "temperature": 0.1,
            "max_tokens": 2000,
            "api_key": "env:OPENAI_API_KEY",
        },
    }
    assert config["mem0"]["embedder"] == {
        "provider": "openai",
        "config": {
            "model": "text-embedding-3-small",
            "api_key": "env:OPENAI_API_KEY",
        },
    }
    assert config["mem0"]["vector_store"] is None
    assert config["openmemory"] == {"custom_instructions": None}


def test_defaults_honor_openai_compatible_env_vars():
    env = {
        "LLM_PROVIDER": "openai",
        "LLM_MODEL": "my-model",
        "LLM_API_KEY": "sk-secret-llm",
        "LLM_BASE_URL": "http://localhost:8080/v1",
        "EMBEDDER_MODEL": "my-embedder",
        "EMBEDDER_API_KEY": "sk-secret-embed",
        "EMBEDDER_BASE_URL": "http://localhost:8081/v1",
    }
    with mock.patch.dict(os.environ, env, clear=True):
        config = get_default_configuration()

    llm = config["mem0"]["llm"]["config"]
    assert llm["model"] == "my-model"
    assert llm["openai_base_url"] == "env:LLM_BASE_URL"
    embedder = config["mem0"]["embedder"]["config"]
    assert embedder["model"] == "my-embedder"
    assert embedder["openai_base_url"] == "env:EMBEDDER_BASE_URL"


def test_defaults_store_env_references_not_secrets():
    """Secret material must never be written into the persisted default config."""
    env = {
        "LLM_MODEL": "my-model",
        "LLM_API_KEY": "sk-secret-llm",
        "EMBEDDER_API_KEY": "sk-secret-embed",
    }
    with mock.patch.dict(os.environ, env, clear=True):
        config = get_default_configuration()

    assert config["mem0"]["llm"]["config"]["api_key"] == "env:LLM_API_KEY"
    assert config["mem0"]["embedder"]["config"]["api_key"] == "env:EMBEDDER_API_KEY"
    assert "sk-secret-llm" not in str(config)
    assert "sk-secret-embed" not in str(config)


def test_defaults_honor_ollama_env_vars():
    env = {
        "LLM_PROVIDER": "ollama",
        "LLM_MODEL": "llama3.1:latest",
        "OLLAMA_BASE_URL": "http://host.docker.internal:11434",
        "EMBEDDER_PROVIDER": "ollama",
        "EMBEDDER_MODEL": "nomic-embed-text",
    }
    with mock.patch.dict(os.environ, env, clear=True):
        config = get_default_configuration()

    llm = config["mem0"]["llm"]
    assert llm["provider"] == "ollama"
    assert llm["config"]["ollama_base_url"] == "env:OLLAMA_BASE_URL"
    assert "api_key" not in llm["config"]
    embedder = config["mem0"]["embedder"]
    assert embedder["provider"] == "ollama"
    assert embedder["config"]["ollama_base_url"] == "env:OLLAMA_BASE_URL"


# ---------------------------------------------------------------------------
# Schema round-trips
# ---------------------------------------------------------------------------

def test_config_schema_preserves_openai_base_url():
    """PUT payloads with openai_base_url must round-trip instead of being dropped."""
    payload = {
        "mem0": {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "my-model",
                    "temperature": 0.1,
                    "max_tokens": 2000,
                    "api_key": "env:OPENAI_API_KEY",
                    "openai_base_url": "http://localhost:8080/v1",
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "my-embedder",
                    "api_key": "env:OPENAI_API_KEY",
                    "openai_base_url": "http://localhost:8081/v1",
                },
            },
        }
    }

    parsed = ConfigSchema(**payload)

    assert parsed.mem0.llm.config.openai_base_url == "http://localhost:8080/v1"
    assert parsed.mem0.embedder.config.openai_base_url == "http://localhost:8081/v1"
    dumped = parsed.model_dump()
    assert dumped["mem0"]["llm"]["config"]["openai_base_url"] == "http://localhost:8080/v1"
    assert dumped["mem0"]["embedder"]["config"]["openai_base_url"] == "http://localhost:8081/v1"
