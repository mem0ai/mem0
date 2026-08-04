"""Tests for _project.py — project_id + branch resolver."""

from __future__ import annotations

import json
import os
import subprocess


def test_resolve_project_id_from_https_remote(tmp_git_repo):
    from _project import resolve_project_id

    pid = resolve_project_id(str(tmp_git_repo))
    assert pid == "mem0ai-mem0"


def test_resolve_project_id_from_ssh_remote(tmp_git_repo_ssh):
    from _project import resolve_project_id

    pid = resolve_project_id(str(tmp_git_repo_ssh))
    assert pid == "acme-cool-project"


def test_resolve_project_id_fallback_basename(tmp_no_git):
    from _project import resolve_project_id

    pid = resolve_project_id(str(tmp_no_git))
    assert pid == os.path.basename(str(tmp_no_git))


def test_resolve_project_id_from_env(tmp_no_git, monkeypatch):
    from _project import resolve_project_id

    monkeypatch.setenv("MEM0_PROJECT_ID", "my-override")
    pid = resolve_project_id(str(tmp_no_git))
    assert pid == "my-override"


def test_resolve_project_id_from_project_map(tmp_no_git):
    from _project import resolve_project_id, save_project_mapping

    save_project_mapping(str(tmp_no_git), "custom-project")
    pid = resolve_project_id(str(tmp_no_git))
    assert pid == "custom-project"


def test_save_project_mapping_creates_file(tmp_no_git):
    from _project import save_project_mapping

    save_project_mapping(str(tmp_no_git), "test-proj")
    map_path = os.path.expanduser("~/.mem0/project_map.json")
    assert os.path.isfile(map_path)
    with open(map_path) as f:
        data = json.load(f)
    assert data[str(tmp_no_git)] == "test-proj"


def test_resolve_branch_in_git_repo(tmp_git_repo):
    from _project import resolve_branch

    subprocess.run(
        ["git", "checkout", "-b", "feat/test-branch"],
        cwd=tmp_git_repo,
        capture_output=True,
        check=True,
    )
    branch = resolve_branch(str(tmp_git_repo))
    assert branch == "feat/test-branch"


def test_resolve_branch_no_git(tmp_no_git):
    from _project import resolve_branch

    branch = resolve_branch(str(tmp_no_git))
    assert branch == "unknown"


def test_remote_url_to_slug_various_formats():
    from _project import _remote_url_to_slug

    assert _remote_url_to_slug("https://github.com/mem0ai/mem0.git") == "mem0ai-mem0"
    assert _remote_url_to_slug("git@github.com:mem0ai/mem0.git") == "mem0ai-mem0"
    assert _remote_url_to_slug("ssh://git@github.com/acme/app.git") == "acme-app"
    assert _remote_url_to_slug("https://gitlab.com/org/sub/repo.git") == "sub-repo"
    assert _remote_url_to_slug("git@bitbucket.org:team/project.git") == "team-project"


def test_remote_url_to_slug_no_git_suffix():
    from _project import _remote_url_to_slug

    assert _remote_url_to_slug("https://github.com/foo/bar") == "foo-bar"


def test_resolve_project_id_priority_order(tmp_git_repo, monkeypatch):
    """Env var > project_map > git remote > basename."""
    from _project import resolve_project_id, save_project_mapping

    # Git remote gives "mem0ai-mem0"
    assert resolve_project_id(str(tmp_git_repo)) == "mem0ai-mem0"

    # project_map overrides git remote
    save_project_mapping(str(tmp_git_repo), "from-map")
    assert resolve_project_id(str(tmp_git_repo)) == "from-map"

    # Env var overrides everything
    monkeypatch.setenv("MEM0_PROJECT_ID", "from-env")
    assert resolve_project_id(str(tmp_git_repo)) == "from-env"


def test_remote_hash_key_format(tmp_git_repo):
    """_remote_hash_key() returns 'remote:<16-char-hex>' for a repo with a remote."""
    import re

    from _project import _remote_hash_key

    key = _remote_hash_key(str(tmp_git_repo))
    assert re.fullmatch(r"remote:[0-9a-f]{16}", key), (
        f"Expected 'remote:<16-char-hex>', got {key!r}"
    )


def test_remote_hash_key_no_git(tmp_no_git):
    """_remote_hash_key() returns empty string when not in a git repo."""
    from _project import _remote_hash_key

    key = _remote_hash_key(str(tmp_no_git))
    assert key == ""


def test_save_project_mapping_writes_remote_key(tmp_git_repo):
    """save_project_mapping() writes both the CWD key and the remote hash key."""
    import re

    from _project import save_project_mapping

    save_project_mapping(str(tmp_git_repo), "my-project")
    map_path = os.path.expanduser("~/.mem0/project_map.json")
    with open(map_path) as f:
        data = json.load(f)

    assert data[str(tmp_git_repo)] == "my-project"
    remote_keys = [k for k in data if re.fullmatch(r"remote:[0-9a-f]{16}", k)]
    assert remote_keys, "Expected at least one remote:<hash> key in project_map.json"
    assert data[remote_keys[0]] == "my-project"


def test_resolve_project_id_remote_hash_fallback(tmp_git_repo, tmp_path):
    """Moving the project folder: remote hash key is used as fallback."""
    from _project import resolve_project_id, save_project_mapping

    # Save mapping for original location
    save_project_mapping(str(tmp_git_repo), "stable-project")

    # Simulate folder move: resolve using a different CWD path that shares the same remote.
    # We use a second tmp_git_repo with the same remote URL to mimic a renamed directory.
    import subprocess as _sp
    new_repo = tmp_path / "moved_repo"
    new_repo.mkdir()
    _sp.run(["git", "init"], cwd=new_repo, capture_output=True, check=True)
    _sp.run(
        ["git", "remote", "add", "origin", "https://github.com/mem0ai/mem0.git"],
        cwd=new_repo,
        capture_output=True,
        check=True,
    )

    # The new CWD is NOT in project_map, but remote hash should match
    pid = resolve_project_id(str(new_repo))
    assert pid == "stable-project", (
        f"Expected 'stable-project' via remote hash fallback, got {pid!r}"
    )
