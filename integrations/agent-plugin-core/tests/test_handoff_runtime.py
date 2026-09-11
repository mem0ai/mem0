from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError

import pytest

CORE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("handoff_launcher", CORE / "python" / "session_handoff.py")
assert SPEC and SPEC.loader
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)
REVISION = "1" * 40
FILES = {
    "handoff_engine.py": b"def main(argv=None, default_source=None):\n    return 0\n",
    "handoff_sources.py": b"# reader\n",
}


def installation(tmp_path, monkeypatch):
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    manifest = {"revision": REVISION, "files": {name: hashlib.sha256(body).hexdigest() for name, body in FILES.items()}}
    (plugin / "handoff-runtime.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(launcher.Path, "home", lambda: tmp_path)
    requested = []

    def download(url, timeout):
        requested.append(url)
        assert timeout == 30
        return io.BytesIO(FILES[url.rsplit("/", 1)[-1]])

    monkeypatch.setattr(launcher, "urlopen", download)
    return plugin, tmp_path / ".mem0" / "handoff-runtime" / REVISION, requested


def test_standalone_download_is_pinned_then_works_offline(tmp_path, monkeypatch):
    plugin, cache, requested = installation(tmp_path, monkeypatch)
    assert launcher.runtime_root(plugin) == cache
    assert set(requested) == {
        f"https://raw.githubusercontent.com/mem0ai/mem0/{REVISION}/integrations/agent-plugin-core/python/{name}"
        for name in FILES
    }
    assert {name: (cache / name).read_bytes() for name in FILES} == FILES

    def offline(*args, **kwargs):
        raise AssertionError("verified cached runtime must not access the network")

    monkeypatch.setattr(launcher, "urlopen", offline)
    assert launcher.runtime_root(plugin) == cache


def test_canonical_checkout_needs_no_manifest_cache_or_network(tmp_path, monkeypatch):
    for name, body in FILES.items():
        (tmp_path / name).write_bytes(body)
    monkeypatch.setattr(launcher, "urlopen", lambda *args, **kwargs: pytest.fail("unexpected network"))
    assert launcher.runtime_root(tmp_path) == tmp_path
    assert not (tmp_path / ".mem0").exists()


@pytest.mark.parametrize("damage", ["tampered", "missing"])
def test_every_use_detects_and_repairs_damaged_cache(tmp_path, monkeypatch, damage):
    plugin, cache, requested = installation(tmp_path, monkeypatch)
    launcher.runtime_root(plugin)
    target = cache / "handoff_sources.py"
    if damage == "tampered":
        target.write_bytes(b"untrusted code")
    else:
        target.unlink()
    requested.clear()
    assert launcher.runtime_root(plugin) == cache
    assert target.read_bytes() == FILES[target.name]
    assert len(requested) == 1
    assert requested[0].endswith("/handoff_sources.py")


def test_failed_second_download_publishes_no_partial_runtime(tmp_path, monkeypatch):
    plugin, cache, _ = installation(tmp_path, monkeypatch)

    def download(url, timeout):
        if url.endswith("handoff_sources.py"):
            raise URLError("offline")
        return io.BytesIO(FILES["handoff_engine.py"])

    monkeypatch.setattr(launcher, "urlopen", download)
    with pytest.raises(OSError, match="could not download pinned handoff runtime handoff_sources.py"):
        launcher.runtime_root(plugin)
    assert not cache.exists()
    assert list(cache.parent.iterdir()) == []


def test_hash_mismatch_never_replaces_existing_cache(tmp_path, monkeypatch):
    plugin, cache, _ = installation(tmp_path, monkeypatch)
    launcher.runtime_root(plugin)
    (cache / "handoff_sources.py").write_bytes(b"tampered")
    monkeypatch.setattr(launcher, "urlopen", lambda *args, **kwargs: io.BytesIO(b"wrong response"))
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        launcher.runtime_root(plugin)
    assert (cache / "handoff_engine.py").read_bytes() == FILES["handoff_engine.py"]
    assert (cache / "handoff_sources.py").read_bytes() == b"tampered"
    assert list(cache.parent.iterdir()) == [cache]


def test_tampered_cache_cannot_run_offline(tmp_path, monkeypatch, capsys):
    plugin, cache, _ = installation(tmp_path, monkeypatch)
    launcher.runtime_root(plugin)
    (cache / "handoff_engine.py").write_bytes(b"untrusted code")

    def offline(*args, **kwargs):
        raise URLError("offline")

    monkeypatch.setattr(launcher, "urlopen", offline)
    resolve = launcher.runtime_root
    monkeypatch.setattr(launcher, "runtime_root", lambda: resolve(plugin))
    assert launcher.main(["--bundle", "-"]) == 1
    assert "handoff runtime unavailable" in capsys.readouterr().err


@pytest.mark.parametrize(
    "manifest",
    [
        {"revision": "main", "files": {}},
        {"revision": REVISION, "files": {"../../outside.py": "a" * 64}},
        {"revision": REVISION, "files": {name: "not-a-hash" for name in FILES}},
        [],
    ],
)
def test_manifest_rejects_unpinned_or_unexpected_files(tmp_path, monkeypatch, manifest):
    plugin, _, requested = installation(tmp_path, monkeypatch)
    (plugin / "handoff-runtime.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        launcher.runtime_root(plugin)
    assert requested == []


def test_missing_manifest_returns_actionable_error(tmp_path, monkeypatch, capsys):
    resolve = launcher.runtime_root
    monkeypatch.setattr(launcher, "runtime_root", lambda: resolve(tmp_path))
    assert launcher.main([]) == 1
    assert "handoff-runtime.json" in capsys.readouterr().err


def test_launcher_executes_adjacent_engine_with_generic_cli_contract(tmp_path):
    shutil.copy2(CORE / "python" / "session_handoff.py", tmp_path / "session_handoff.py")
    (tmp_path / "handoff_sources.py").write_text("# reader\n")
    (tmp_path / "handoff_engine.py").write_text(
        "import sys\ndef main(argv=None, default_source='unexpected'):\n"
        "    assert default_source is None\n    assert sys.argv[1:] == ['--bundle', '-']\n    return 7\n"
    )
    result = subprocess.run(
        [sys.executable, str(tmp_path / "session_handoff.py"), "--bundle", "-"], capture_output=True
    )
    assert result.returncode == 7, result.stderr.decode()


def test_manifest_declares_only_launcher_and_hashes_pinned_engines():
    manifest = json.loads((CORE / "build" / "handoff-runtime.json").read_text())
    assert manifest["artifacts"] == ["session_handoff.py", "handoff-runtime.json"]
    assert len(manifest["revision"]) == 40 and all(char in "0123456789abcdef" for char in manifest["revision"])
    assert set(manifest["files"]) == launcher.ENGINE_FILES
    for name, digest in manifest["files"].items():
        assert digest == hashlib.sha256((CORE / "python" / name).read_bytes()).hexdigest()
