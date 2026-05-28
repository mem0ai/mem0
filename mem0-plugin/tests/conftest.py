"""Shared fixtures for mem0-plugin tests."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")


@pytest.fixture(autouse=True)
def _scripts_on_path():
    """Ensure scripts/ is on sys.path so we can import _project, session_stats, etc."""
    abs_scripts = os.path.abspath(SCRIPTS_DIR)
    if abs_scripts not in sys.path:
        sys.path.insert(0, abs_scripts)
    yield
    if abs_scripts in sys.path:
        sys.path.remove(abs_scripts)


@pytest.fixture(autouse=True)
def _clean_project_map(monkeypatch):
    """Remove project_map.json and clear MEM0_PROJECT_ID before each test."""
    monkeypatch.delenv("MEM0_PROJECT_ID", raising=False)
    map_path = os.path.expanduser("~/.mem0/project_map.json")
    if os.path.isfile(map_path):
        os.remove(map_path)
    yield
    if os.path.isfile(map_path):
        os.remove(map_path)


@pytest.fixture()
def tmp_git_repo(tmp_path):
    """Create a temp dir with a git repo and HTTPS remote."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/mem0ai/mem0.git"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    return tmp_path


@pytest.fixture()
def tmp_git_repo_ssh(tmp_path):
    """Create a temp dir with a git repo and SSH remote."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "git@github.com:acme/cool-project.git"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    return tmp_path


@pytest.fixture()
def tmp_no_git(tmp_path):
    """Temp dir with no git repo."""
    return tmp_path
