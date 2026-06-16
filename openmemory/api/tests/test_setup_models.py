"""Tests for the install-time model-selection CLI entrypoint (task_09).

``python -m app.setup_models`` is a thin wrapper around
``setup_models_interactive``; these tests assert the argument wiring (persist
toggle, non-interactive --yes path, validation) without touching Ollama or the
database.
"""

import os
from unittest.mock import patch

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest

from app import setup_models


def test_yes_requires_llm_and_embedder():
    # --yes without both model names is a usage error (exit code 2), no call.
    with patch("app.utils.model_detection.setup_models_interactive") as m:
        rc = setup_models.main(["--yes", "--llm", "only-llm"])
    assert rc == 2
    m.assert_not_called()


def test_non_interactive_passes_models_and_persists_by_default():
    captured = {}

    def fake_setup(ollama_base_url=None, input_func=None, persist=False):
        # Reproduce how the flow consumes answers: LLM then embedder.
        captured["llm"] = input_func("llm? ")
        captured["embedder"] = input_func("embedder? ")
        captured["persist"] = persist
        return {"llm": {"config": {"model": captured["llm"]}},
                "embedder": {"config": {"model": captured["embedder"]}}}

    with patch("app.utils.model_detection.setup_models_interactive", fake_setup):
        rc = setup_models.main(["--yes", "--llm", "L1", "--embedder", "E1"])

    assert rc == 0
    assert captured["llm"] == "L1"
    assert captured["embedder"] == "E1"
    assert captured["persist"] is True  # persists unless --no-persist


def test_no_persist_flag_disables_persistence():
    seen = {}

    def fake_setup(ollama_base_url=None, input_func=None, persist=False):
        seen["persist"] = persist
        return {"llm": {}, "embedder": {}}

    with patch("app.utils.model_detection.setup_models_interactive", fake_setup):
        rc = setup_models.main(
            ["--yes", "--llm", "L", "--embedder", "E", "--no-persist"]
        )

    assert rc == 0
    assert seen["persist"] is False


def test_ollama_url_is_forwarded():
    seen = {}

    def fake_setup(ollama_base_url=None, input_func=None, persist=False):
        seen["url"] = ollama_base_url
        return {"llm": {}, "embedder": {}}

    with patch("app.utils.model_detection.setup_models_interactive", fake_setup):
        setup_models.main(
            ["--yes", "--llm", "L", "--embedder", "E",
             "--ollama-url", "http://192.168.0.10:11434"]
        )

    assert seen["url"] == "http://192.168.0.10:11434"
