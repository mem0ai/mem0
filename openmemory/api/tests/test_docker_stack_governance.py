"""Docker stack governance worker validation (task_13)."""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

STACK = Path(__file__).resolve().parents[2] / "docker-stack.yml"


@pytest.fixture(scope="module")
def stack():
    return yaml.safe_load(STACK.read_text(encoding="utf-8"))


def test_governance_worker_service_exists(stack):
    assert "openmemory-governance-worker" in stack["services"]


def test_governance_worker_command(stack):
    svc = stack["services"]["openmemory-governance-worker"]
    assert svc["command"] == "python -m app.workers.governance_worker"


def test_governance_worker_singleton(stack):
    assert stack["services"]["openmemory-governance-worker"]["deploy"]["replicas"] == 1


def test_governance_worker_env(stack):
    env = stack["services"]["openmemory-governance-worker"]["environment"]
    assert env["RUN_EMBEDDED_WORKER"] == "false"
    assert "DATABASE_URL" in env
    assert "QDRANT_HOST" in env
    assert "REDIS_URL" in env


def test_governance_worker_restart_policy(stack):
    policy = stack["services"]["openmemory-governance-worker"]["deploy"]["restart_policy"]
    assert policy["condition"] == "on-failure"
