"""Keep every executable hosted-memory ingress behind a named adapter."""

from __future__ import annotations

from pathlib import Path


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN / "scripts"


def test_direct_urlopen_has_one_memory_transport_owner():
    offenders = []
    for path in SCRIPTS.glob("*"):
        if path.suffix not in {".py", ".sh"}:
            continue
        text = path.read_text(errors="replace")
        if "urllib.request.urlopen" not in text:
            continue
        if path.name not in {"hosted_request.py", "telemetry.py"}:
            offenders.append(path.name)
    assert offenders == []


def test_every_api_url_builder_imports_transport_adapter():
    exclusions = {"hosted_request.py", "telemetry.py"}
    offenders = []
    for path in SCRIPTS.glob("*.py"):
        text = path.read_text(errors="replace")
        if "api.mem0.ai" in text and path.name not in exclusions:
            if "open_hosted_request" not in text:
                offenders.append(path.name)
    assert offenders == []


def test_every_sdk_call_site_has_admission_bridge():
    offenders = []
    for path in SCRIPTS.glob("*.py"):
        text = path.read_text(errors="replace")
        if "MemoryClient" in text and "require_admission" not in text:
            offenders.append(path.name)
    assert offenders == []


def test_opencode_surface_is_explicitly_excluded_from_p0():
    opencode = PLUGIN / ".opencode-plugin" / "opencode-mem0.ts"
    assert opencode.exists()
    assert "P0 cost admission: unprotected" in (PLUGIN / "README.md").read_text()
