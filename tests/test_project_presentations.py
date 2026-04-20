from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "build_project_presentations.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("build_project_presentations", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_slides_reads_markdown_decks() -> None:
    module = _load_module()
    source = (ROOT / "docs" / "presentations" / "agent-memory-runtime-for-builders.md").read_text(encoding="utf-8")

    slides = module.parse_slides(source)

    assert len(slides) >= 8
    assert slides[0].title == "Agent Memory Runtime"
    assert slides[1].subtitle is not None


def test_build_single_deck_generates_pdf(tmp_path: Path) -> None:
    module = _load_module()
    source = ROOT / "docs" / "presentations" / "agent-memory-runtime-for-executives.md"
    output = tmp_path / "executive.pdf"

    module.build_deck(source, output, module.EXECUTIVE_THEME)

    data = output.read_bytes()
    assert data.startswith(b"%PDF-1.4")
    assert len(data) > 1500
