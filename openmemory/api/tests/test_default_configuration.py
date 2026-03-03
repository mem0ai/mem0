import json
from pathlib import Path

from app.routers import config as config_router


def test_get_default_configuration_reads_file(tmp_path, monkeypatch):
    # Build a fake module file path so parents[2]/default_config.json resolves into tmp_path
    fake_module = tmp_path / "api" / "app" / "routers" / "config.py"
    fake_module.parent.mkdir(parents=True)
    fake_module.write_text("# fake", encoding="utf-8")

    defaults_path = tmp_path / "api" / "default_config.json"
    defaults_path.parent.mkdir(parents=True, exist_ok=True)
    defaults_path.write_text(
        json.dumps(
            {
                "openmemory": {"custom_instructions": "from-file"},
                "mem0": {
                    "llm": {"provider": "openai", "config": {"model": "gpt-4o-mini"}},
                    "embedder": {"provider": "openai", "config": {"model": "text-embedding-3-small"}},
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(config_router, "__file__", str(fake_module))

    cfg = config_router.get_default_configuration()
    assert cfg["openmemory"]["custom_instructions"] == "from-file"
    assert cfg["mem0"]["llm"]["provider"] == "openai"
    assert "vector_store" in cfg["mem0"]


def test_get_default_configuration_fallback_when_file_unavailable(monkeypatch):
    monkeypatch.setattr(Path, "read_text", lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()))
    cfg = config_router.get_default_configuration()
    assert cfg["mem0"]["llm"]["provider"] == "openai"
    assert cfg["mem0"]["embedder"]["provider"] == "openai"
    assert "vector_store" in cfg["mem0"]
