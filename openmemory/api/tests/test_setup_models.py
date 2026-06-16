"""Tests for the install-time model-selection CLI entrypoint (task_09).

``python -m app.setup_models`` wraps the detection/selection flow for both local
backends (Ollama + llama.cpp). These tests assert the argument wiring (backend
choice, non-interactive --yes build, persistence toggle) without touching the
network or the database.
"""

import os
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest

from app import setup_models


def test_yes_requires_llm_and_embedder():
    with patch("app.utils.memory.persist_model_selection") as persist:
        rc = setup_models.main(["--yes", "--llm", "only-llm"])
    assert rc == 2
    persist.assert_not_called()


def test_yes_builds_ollama_by_default_and_persists():
    captured = {}
    with patch("app.utils.memory.persist_model_selection",
               side_effect=lambda cfg: captured.setdefault("cfg", cfg)):
        rc = setup_models.main(["--yes", "--llm", "llama3.1:latest",
                                "--embedder", "nomic-embed-text"])
    assert rc == 0
    cfg = captured["cfg"]
    assert cfg["llm"]["provider"] == "ollama"  # auto -> ollama with explicit names
    assert cfg["llm"]["config"]["model"] == "llama3.1:latest"


def test_yes_backend_llamacpp_builds_openai_config():
    captured = {}
    with patch("app.utils.memory.persist_model_selection",
               side_effect=lambda cfg: captured.setdefault("cfg", cfg)):
        rc = setup_models.main(["--backend", "llamacpp", "--yes",
                                "--llm", "qwen2.5:7b", "--embedder", "nomic",
                                "--llamacpp-url", "http://host.docker.internal:8080"])
    assert rc == 0
    cfg = captured["cfg"]
    assert cfg["llm"]["provider"] == "openai"
    assert cfg["llm"]["config"]["openai_base_url"] == "http://host.docker.internal:8080/v1"


def test_no_persist_flag_skips_persistence():
    with patch("app.utils.memory.persist_model_selection") as persist:
        rc = setup_models.main(["--yes", "--llm", "L", "--embedder", "E",
                                "--no-persist"])
    assert rc == 0
    persist.assert_not_called()


def test_interactive_forwards_backend_and_urls():
    seen = {}

    def fake_setup(**kwargs):
        seen.update(kwargs)
        return {"llm": {}, "embedder": {}}

    with patch("app.utils.model_detection.setup_models_interactive", fake_setup):
        rc = setup_models.main(["--backend", "auto",
                                "--ollama-url", "http://o:11434",
                                "--llamacpp-url", "http://l:8080"])
    assert rc == 0
    assert seen["backend"] == "auto"
    assert seen["ollama_base_url"] == "http://o:11434"
    assert seen["llamacpp_base_url"] == "http://l:8080"
    assert seen["persist"] is True  # persists unless --no-persist
