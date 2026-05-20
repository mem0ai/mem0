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
