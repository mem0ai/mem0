"""Tests for governance policy resolver (task_02)."""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Config, GovernancePolicy, Project
from app.utils.governance_policy import (
    DEFAULT_POLICY,
    merge_policy,
    resolve_policy,
    validate_policy_document,
)


@pytest.fixture
def session_factory(tmp_path):
    db_path = tmp_path / "policy.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine)

    def _factory():
        return factory()

    return _factory


def test_project_without_override_inherits_global(session_factory):
    db = session_factory()
    db.add(Config(key="governance", value={"ttl_max_age_days": 400}))
    db.add(Project(name="p1"))
    db.commit()
    db.close()

    policy = resolve_policy("p1", session_factory=session_factory)
    assert policy.ttl_max_age_days == 400
    assert policy.ttl_idle_days == DEFAULT_POLICY["ttl_idle_days"]


def test_override_partial_merge(session_factory):
    db = session_factory()
    db.add(Config(key="governance", value={"ttl_max_age_days": 400, "ttl_idle_days": 80}))
    db.add(Project(name="p1"))
    db.add(GovernancePolicy(project_name="p1", overrides={"ttl_idle_days": 120}))
    db.commit()
    db.close()

    policy = resolve_policy("p1", session_factory=session_factory)
    assert policy.ttl_max_age_days == 400
    assert policy.ttl_idle_days == 120


def test_missing_global_fields_use_defaults():
    doc = validate_policy_document({})
    assert doc["quarantine_window_days"] == DEFAULT_POLICY["quarantine_window_days"]


def test_invalid_similarity_threshold():
    with pytest.raises(ValidationError):
        validate_policy_document({"similarity_threshold": 1.5})


def test_invalid_tiebreak():
    with pytest.raises(ValidationError):
        validate_policy_document({"contradiction_tiebreak": "votes"})


def test_merge_policy_deterministic():
    merged = merge_policy({"ttl_max_age_days": 100}, {"ttl_idle_days": 10})
    assert merged["ttl_max_age_days"] == 100
    assert merged["ttl_idle_days"] == 10
