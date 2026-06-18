"""Tests for read/write routing helpers (task_04 / ADR-002 / ADR-003).

Verifies that the read/write paths bind the client's vector store to the active
collection and route project-scoped reads to the project's shard key, using the
``bind_active_collection`` / ``resolve_and_bind`` helpers. SQLite-backed; no
Qdrant required.
"""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, MigrationState, PartitionTier, Project
from app.utils.partitioning import (
    PartitionResolver,
    bind_active_collection,
    resolve_and_bind,
)


class _FakeVectorStore:
    def __init__(self, collection_name="openmemory"):
        self.collection_name = collection_name


class _FakeClient:
    def __init__(self, collection_name="openmemory"):
        self.vector_store = _FakeVectorStore(collection_name)


@pytest.fixture
def factory():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(autocommit=False, autoflush=False, bind=engine)
    engine.dispose()


def _resolver(factory):
    return PartitionResolver(session_factory=factory, default_collection="openmemory")


def test_resolve_and_bind_sets_collection_and_shard_key(factory):
    db = factory()
    db.add(Project(name="big", partition_tier=PartitionTier.dedicated, shard_key="big"))
    db.add(
        MigrationState(
            source_collection="blue",
            target_collection="green",
            active_collection="green",
        )
    )
    db.commit()
    db.close()

    client = _FakeClient()
    route = resolve_and_bind(client, "big", resolver=_resolver(factory))

    assert client.vector_store.collection_name == "green"
    assert route.shard_key == "big"


def test_resolve_and_bind_shared_project_no_shard_key(factory):
    db = factory()
    db.add(Project(name="small"))
    db.add(
        MigrationState(
            source_collection="blue",
            target_collection="green",
            active_collection="blue",
        )
    )
    db.commit()
    db.close()

    client = _FakeClient()
    route = resolve_and_bind(client, "small", resolver=_resolver(factory))

    assert client.vector_store.collection_name == "blue"
    assert route.shard_key is None


def test_bind_active_collection_sets_collection(factory):
    db = factory()
    db.add(
        MigrationState(
            source_collection="blue",
            target_collection="green",
            active_collection="green",
        )
    )
    db.commit()
    db.close()

    client = _FakeClient()
    active = bind_active_collection(client, resolver=_resolver(factory))

    assert active == "green"
    assert client.vector_store.collection_name == "green"


def test_routing_falls_back_when_no_state(factory):
    # Empty DB (no migration_state row): keep the env-configured collection.
    client = _FakeClient(collection_name="openmemory")
    active = bind_active_collection(client, resolver=_resolver(factory))
    assert active == "openmemory"
    assert client.vector_store.collection_name == "openmemory"


def test_bind_is_noop_when_already_bound(factory):
    db = factory()
    db.add(
        MigrationState(
            source_collection="blue",
            target_collection="blue",
            active_collection="blue",
        )
    )
    db.commit()
    db.close()

    client = _FakeClient(collection_name="blue")
    # Should not raise and keeps the same collection.
    bind_active_collection(client, resolver=_resolver(factory))
    assert client.vector_store.collection_name == "blue"


def test_missing_state_table_is_tolerated():
    # Resolver pointed at a DB without the partitioning tables must not raise.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine)  # no create_all -> tables absent
    client = _FakeClient()
    active = bind_active_collection(
        client, resolver=PartitionResolver(session_factory=factory, default_collection="openmemory")
    )
    assert active == "openmemory"
    engine.dispose()
