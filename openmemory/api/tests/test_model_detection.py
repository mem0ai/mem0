"""Tests for install-time Ollama model detection (task_09 / ADR-006).

Covers:
- ``detect_ollama_models`` parsing a mocked ``Client.list()`` with 2 models.
- Selecting an LLM + embedder builds an ``ollama`` config consumable by
  ``Memory.from_config``.
- ``list()`` raising triggers the manual fallback (no crash).
- ``pull()`` is never called by the detection / setup step.
"""

import os
from unittest.mock import Mock, patch

import pytest

from app.utils import model_detection
from app.utils.model_detection import (
    OllamaUnavailableError,
    build_ollama_runtime_config,
    detect_ollama_models,
    setup_models_interactive,
)


@pytest.fixture
def two_model_client():
    """An Ollama client whose list() returns two installed models."""
    client = Mock()
    client.list.return_value = {
        "models": [
            {"name": "llama3.1:latest"},
            {"name": "nomic-embed-text:latest"},
        ]
    }
    return client


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def test_detect_returns_both_model_names(two_model_client):
    names = detect_ollama_models(client=two_model_client)

    assert names == ["llama3.1:latest", "nomic-embed-text:latest"]
    two_model_client.list.assert_called_once()
    # Detection must never trigger a download.
    two_model_client.pull.assert_not_called()


def test_detect_supports_model_key_variant():
    """Newer Ollama payloads expose 'model' instead of 'name'."""
    client = Mock()
    client.list.return_value = {"models": [{"model": "phi3:latest"}]}

    assert detect_ollama_models(client=client) == ["phi3:latest"]


def test_detect_empty_list_returns_empty(two_model_client):
    two_model_client.list.return_value = {"models": []}

    assert detect_ollama_models(client=two_model_client) == []


def test_detect_supports_object_style_model_entries():
    """Newer ollama clients return objects (with .name/.model), not dicts."""
    client = Mock()
    entry = Mock(spec=["name", "model"])
    entry.name = "llama3.1:latest"
    entry.model = None
    client.list.return_value = {"models": [entry]}

    assert detect_ollama_models(client=client) == ["llama3.1:latest"]


def test_detect_supports_object_style_response():
    """The whole list() response may be an object exposing .models."""
    client = Mock()
    response = Mock(spec=["models"])
    response.models = [{"name": "phi3:latest"}]
    client.list.return_value = response

    assert detect_ollama_models(client=client) == ["phi3:latest"]


def test_detect_client_construction_error_raises_unavailable():
    """If building the Ollama client raises, surface OllamaUnavailableError."""
    with patch.object(model_detection, "Client", side_effect=RuntimeError("boom")):
        with pytest.raises(OllamaUnavailableError):
            detect_ollama_models(ollama_base_url="http://example:11434")


def test_detect_uses_constructed_client_with_base_url():
    """When no client is injected, one is built against the resolved base URL."""
    fake_client = Mock()
    fake_client.list.return_value = {"models": [{"name": "llama3.1:latest"}]}

    with patch.object(model_detection, "Client", return_value=fake_client) as ctor:
        names = detect_ollama_models(ollama_base_url="http://example:11434")

    ctor.assert_called_once_with(host="http://example:11434")
    assert names == ["llama3.1:latest"]


def test_detect_missing_library_raises_unavailable():
    with patch.object(model_detection, "Client", None):
        with pytest.raises(OllamaUnavailableError):
            detect_ollama_models()


def test_detect_list_error_raises_unavailable():
    client = Mock()
    client.list.side_effect = ConnectionError("connection refused")

    with pytest.raises(OllamaUnavailableError):
        detect_ollama_models(client=client)
    # Even on failure, no download attempt.
    client.pull.assert_not_called()


# ---------------------------------------------------------------------------
# Runtime config building
# ---------------------------------------------------------------------------

def test_build_runtime_config_shapes_ollama_providers():
    config = build_ollama_runtime_config(
        llm_model="llama3.1:latest",
        embedder_model="nomic-embed-text:latest",
        ollama_base_url="http://localhost:11434",
    )

    assert config["llm"]["provider"] == "ollama"
    assert config["llm"]["config"]["model"] == "llama3.1:latest"
    assert config["embedder"]["provider"] == "ollama"
    assert config["embedder"]["config"]["model"] == "nomic-embed-text:latest"
    assert config["llm"]["config"]["ollama_base_url"] == "http://localhost:11434"
    assert config["embedder"]["config"]["ollama_base_url"] == "http://localhost:11434"


def test_build_runtime_config_requires_models():
    with pytest.raises(ValueError):
        build_ollama_runtime_config(llm_model="", embedder_model="x")
    with pytest.raises(ValueError):
        build_ollama_runtime_config(llm_model="x", embedder_model="")


def test_build_runtime_config_consumable_by_memory_from_config():
    """The produced config dict must validate against mem0's config model."""
    config = build_ollama_runtime_config(
        llm_model="llama3.1:latest",
        embedder_model="nomic-embed-text:latest",
    )

    from mem0.configs.base import MemoryConfig

    validated = MemoryConfig(**config)
    assert validated.llm.provider == "ollama"
    assert validated.embedder.provider == "ollama"
    assert validated.llm.config["model"] == "llama3.1:latest"
    assert validated.embedder.config["model"] == "nomic-embed-text:latest"


# ---------------------------------------------------------------------------
# Interactive setup flow
# ---------------------------------------------------------------------------

def test_setup_selects_from_detected_list_by_number(two_model_client):
    answers = iter(["1", "2"])  # LLM -> model 1, embedder -> model 2
    config = setup_models_interactive(
        client=two_model_client,
        input_func=lambda _prompt: next(answers),
    )

    assert config["llm"]["config"]["model"] == "llama3.1:latest"
    assert config["embedder"]["config"]["model"] == "nomic-embed-text:latest"
    two_model_client.pull.assert_not_called()


def test_setup_selects_by_typed_name(two_model_client):
    answers = iter(["llama3.1:latest", "nomic-embed-text:latest"])
    config = setup_models_interactive(
        client=two_model_client,
        input_func=lambda _prompt: next(answers),
    )

    assert config["llm"]["config"]["model"] == "llama3.1:latest"
    assert config["embedder"]["config"]["model"] == "nomic-embed-text:latest"


def test_setup_falls_back_to_manual_when_unavailable():
    """When list() raises, the flow asks for manual model names (no crash)."""
    client = Mock()
    client.list.side_effect = ConnectionError("ollama down")

    answers = iter(["my-llm", "my-embedder"])
    config = setup_models_interactive(
        client=client,
        input_func=lambda _prompt: next(answers),
    )

    assert config["llm"]["config"]["model"] == "my-llm"
    assert config["embedder"]["config"]["model"] == "my-embedder"
    assert config["llm"]["provider"] == "ollama"
    assert config["embedder"]["provider"] == "ollama"
    client.pull.assert_not_called()


def test_setup_never_triggers_pull(two_model_client):
    answers = iter(["1", "2"])
    setup_models_interactive(
        client=two_model_client,
        input_func=lambda _prompt: next(answers),
    )
    two_model_client.pull.assert_not_called()


# ---------------------------------------------------------------------------
# Persisting the selection into the runtime config (task_09.3)
# ---------------------------------------------------------------------------

def test_setup_persists_selection_when_requested(two_model_client):
    """persist=True routes the chosen config to the persistence callback."""
    answers = iter(["1", "2"])
    captured = {}
    config = setup_models_interactive(
        client=two_model_client,
        input_func=lambda _prompt: next(answers),
        persist=True,
        persist_func=lambda cfg: captured.setdefault("cfg", cfg),
    )

    assert captured["cfg"] is config
    assert captured["cfg"]["llm"]["config"]["model"] == "llama3.1:latest"


def test_setup_does_not_persist_by_default(two_model_client):
    answers = iter(["1", "2"])
    captured = {}
    setup_models_interactive(
        client=two_model_client,
        input_func=lambda _prompt: next(answers),
        persist_func=lambda cfg: captured.setdefault("cfg", cfg),
    )
    assert captured == {}  # persist defaults to False


def _config_factory():
    """In-memory sqlite sessionmaker with just the configs table."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models import Config as ConfigModel

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    ConfigModel.__table__.create(bind=engine, checkfirst=True)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_persist_model_selection_writes_runtime_config():
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    from app.models import Config as ConfigModel
    from app.utils import memory as memory_mod

    factory = _config_factory()
    runtime_config = build_ollama_runtime_config(
        llm_model="llama3.1:latest",
        embedder_model="nomic-embed-text:latest",
    )

    with patch.object(memory_mod, "reset_memory_client") as reset:
        mem0_cfg = memory_mod.persist_model_selection(
            runtime_config, session_factory=factory
        )

    # The selection lands in the 'main' config row under the mem0 key, where
    # get_memory_client reads it from — so it drives the runtime client.
    assert mem0_cfg["llm"]["config"]["model"] == "llama3.1:latest"
    assert mem0_cfg["embedder"]["config"]["model"] == "nomic-embed-text:latest"
    reset.assert_called_once()

    db = factory()
    try:
        row = db.query(ConfigModel).filter(ConfigModel.key == "main").first()
        assert row is not None
        assert row.value["mem0"]["llm"]["config"]["model"] == "llama3.1:latest"
    finally:
        db.close()


def test_persist_model_selection_merges_existing_config():
    """Persisting must not clobber unrelated settings (e.g. custom_instructions)."""
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    from app.models import Config as ConfigModel
    from app.utils import memory as memory_mod

    factory = _config_factory()
    db = factory()
    try:
        db.add(ConfigModel(key="main", value={
            "openmemory": {"custom_instructions": "keep me"},
            "mem0": {"vector_store": {"provider": "qdrant"}},
        }))
        db.commit()
    finally:
        db.close()

    runtime_config = build_ollama_runtime_config(
        llm_model="llama3.1:latest", embedder_model="nomic-embed-text:latest",
    )
    with patch.object(memory_mod, "reset_memory_client"):
        memory_mod.persist_model_selection(runtime_config, session_factory=factory)

    db = factory()
    try:
        row = db.query(ConfigModel).filter(ConfigModel.key == "main").first()
        assert row.value["openmemory"]["custom_instructions"] == "keep me"
        assert row.value["mem0"]["vector_store"]["provider"] == "qdrant"
        assert row.value["mem0"]["llm"]["config"]["model"] == "llama3.1:latest"
    finally:
        db.close()


def test_persist_model_selection_rejects_incomplete_config():
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    from app.utils import memory as memory_mod

    with pytest.raises(ValueError):
        memory_mod.persist_model_selection({"llm": {}}, session_factory=_config_factory())


# ---------------------------------------------------------------------------
# memory.py wrappers stay working
# ---------------------------------------------------------------------------

def test_memory_module_wrappers_delegate(two_model_client):
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    from app.utils import memory as memory_mod

    names = memory_mod.detect_ollama_models(client=two_model_client)
    assert names == ["llama3.1:latest", "nomic-embed-text:latest"]

    config = memory_mod.build_ollama_runtime_config(
        llm_model="llama3.1:latest",
        embedder_model="nomic-embed-text:latest",
    )
    assert config["llm"]["provider"] == "ollama"
    assert config["embedder"]["provider"] == "ollama"
