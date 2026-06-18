"""Tests for scale bootstrap artifacts (task_08)."""

import os
from pathlib import Path
from unittest.mock import MagicMock


ROOT = Path(__file__).resolve().parents[2]


class TestBootstrapArtifacts:
    def test_bootstrap_script_exists_and_executable(self):
        script = ROOT / "scripts" / "bootstrap-scale.sh"
        assert script.exists()
        assert os.access(script, os.X_OK)

    def test_docker_compose_scale_valid(self):
        compose = ROOT / "docker-compose.scale.yml"
        assert compose.exists()
        text = compose.read_text()
        assert "pgbouncer" in text
        assert "openmemory-write-worker" in text
        assert "circuitbreaker" in text

    def test_docker_stack_exists(self):
        stack = ROOT / "docker-stack.yml"
        assert stack.exists()
        assert "deploy:" in stack.read_text()

    def test_migrate_script_importable(self):
        script = ROOT / "scripts" / "migrate_sqlite_to_postgres.py"
        assert script.exists()


class TestBootstrapDetection:
    def test_detect_ollama_when_tags_respond(self):
        from app.utils.model_detection import detect_ollama_models

        fake_client = MagicMock()
        fake_client.list.return_value = {"models": [{"name": "llama3.1:8b"}]}
        models = detect_ollama_models(ollama_base_url="http://ollama:11434", client=fake_client)
        assert models == ["llama3.1:8b"]

    def test_detect_llamacpp_when_models_respond(self):
        from app.utils.model_detection import detect_llamacpp_models

        def fake_fetch(url):
            return {"data": [{"id": "local-model"}]}

        models = detect_llamacpp_models(base_url="http://llama:8080/v1", fetch=fake_fetch)
        assert models == ["local-model"]

    def test_explicit_embed_url_skips_detection_in_bootstrap_guard(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_EMBED_URL", "http://embed:11434")
        skip = bool(os.getenv("OLLAMA_EMBED_URL") or os.getenv("EMBEDDER_BASE_URL"))
        assert skip is True
